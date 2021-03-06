import configparser

from core.exceptions.generic_exceptions import NotExistingResource
from core.exceptions.session_exceptions import SessionValidationException, \
    IllegalSessionStateException
from core.helpers.loggers import LoggerHelper
from core.helpers.mongo import MongoHelper
from core.helpers.validators import SessionValidator, GenericValidator, FilesValidator
from core.model.rumba_session import RumbaSession
from core.model.session_status import SessionStatus
from core.services.audio_manager import AudioManager
from core.services.fs_manager import FileSystemService

LOGGER = LoggerHelper.get_logger("session_manager", "session_manager.log")


CONFIG = configparser.RawConfigParser()
CONFIG.read('backend.cfg')

SERVER_URL = CONFIG.get("server", "server_url")
if SERVER_URL[-1] != "/":
    SERVER_URL = SERVER_URL + "/"


class SessionManager(object):
    __instance = None

    def __init__(self):
        if SessionManager.__instance is not None:
            raise Exception("This class is a singleton.")
        else:
            SessionManager.__instance = self

    @staticmethod
    def get_instance():
        if not SessionManager.__instance:
            SessionManager()
        return SessionManager.__instance

    def create_session(self, session_info):
        """
        Creates a new Rumba session.

        A session is composed by information about the event, such as the concert name, the band
        and the concert's date.

        A session can only be created if there's no other active or created session. If the session could be
        successfully created, a directory will be created in the FS for storing all the files
        associated to this new RUMBA session.
        
        :param session_info: Dictionary containing the information of the session. Mandatory fields
        are:
            - concert: String containing the name of the concert.
            - band: String containing the name of the band.
            - date: Date of the concert in timestamp format.
            - is_public: Boolean indicating if the concert is public or not.
        :return: String containing the id of the created session.
        :rtype: str
        :raises: SessionValidationException, if there's any error with the information provided as
        parameter.
        """
        LOGGER.info("Creating new session.")
        LOGGER.debug("Validating user input: {}".format(session_info))
        try:
            # First we validate user input
            SessionValidator.validate_new_session(session_info)
            LOGGER.info("Checking if there's any active sessions..")
            created_sessions = RumbaSession.objects(state=SessionStatus.CREATED.value).count()
            active_sessions = RumbaSession.objects(state=SessionStatus.ACTIVE.value).count()
            if active_sessions > 0 or created_sessions > 0:
                LOGGER.error("Error creating session: There's already an active session.")
                raise SessionValidationException("There's already an active session.")
            # Secondly we create the working directory.
            dir_path = FileSystemService.get_instance().create_session_directory(
                band=session_info['band'])

        except Exception as ex:
            LOGGER.exception("Error creating session  - ")
            raise ex
        try:
            # Store the information int the DB.
            session = RumbaSession(concert=session_info['concert'], band=session_info['band'],
                                   date=session_info['date'], folder_url=dir_path, location=session_info['location']
                                   ).save()
            session.update(set__edition_url="{}editor-nice/{}".format(SERVER_URL, str(session['id'])))
            session.update(set__record_url="{}camera-back".format(SERVER_URL))
            session.update(set__master_url="{}master-camera".format(SERVER_URL))
            LOGGER.info(
                "Session successfully created: [id={0}, band={1}]".format(str(session['id']),
                                                                          session['band']))
            return str(session['id'])
        except Exception as ex:
            LOGGER.exception("Error storing session in DB - Executing rollback...")
            FileSystemService.get_instance().delete_session_directory(
                band=session_info['band'])
            raise ex

    def initialize_session(self, session_id):
        """
        Initialize a created session.

        A session can only be initialized from the "Created" state. When a session is initialized,
        it starts to record the audio and its state is modified to "Active" state.

        :param session_id: Session to be created
        :raises:
        - IllegalSessionStateException, if the session is no in the "Created" state.
        - NotExistingResource, if there's no session with such id.
        """
        LOGGER.info("Initializing session. [session_id={}]".format(session_id))
        GenericValidator.validate_id(session_id)
        session = RumbaSession.objects(id=session_id).first()
        if session is None:
            raise NotExistingResource("There's no session with such id.")
        if session['state'] != SessionStatus.CREATED.value:
            raise IllegalSessionStateException("Session can only be initialized from 'Created' state")
        LOGGER.debug("Initializing audio record.")
        initial_timestmap = AudioManager.get_instance().record_audio(session['folder_url'])
        try:
            LOGGER.debug("Updating session state.")
            session.update(set__state=SessionStatus.ACTIVE.value, set__audio_timestamp=str(initial_timestmap))
        except Exception as ex:
            LOGGER.exception("Could not update session state. Stopping audio recording...")
            AudioManager.get_instance().stop_audio()
            raise ex

    def get_session(self, session_id):
        """
        Retrieves and returns the session identified with the given id.

        This method check if there's a session in the database with the provided id. If so, the
        information of the session is returned in a dictionary. If not, the method raises a
        IllegalSessionStateException.
        :return: Dictionary containing the information of the session identified with the id given
        as parameter.
        :raises:
        - NotExistingResource, if there's no session with such id.
        - ValueError, if the provided id is not a valid id.
        """
        LOGGER.info("Retrieveing session: [id={}].".format(session_id))
        GenericValidator.validate_id(session_id)
        session = RumbaSession.objects(id=session_id).first()
        if session is None:
            raise NotExistingResource("There's no session with such id.")
        LOGGER.info("Session successfully retrieved: [id={}]".format(session_id))
        LOGGER.debug("Session information: {}".format(session))
        view_sess = MongoHelper.to_dict(session)
        view_sess.pop('folder_url')
        return view_sess

    def list_sessions(self):
        """
        Retrieves and returns all managed sessions.

        This method querys mongo database in order to retrieve all the sessions. Each session
        is transformed into a d ictionary and returned as an element of the list.
        :return: List of managed sessions. Each position of the list is a dictionary representing
        a session.
        """
        LOGGER.info("Retrieving all sessions.")
        session_list = []
        sessions = RumbaSession.objects()
        for session in sessions:
            view_sess = MongoHelper.to_dict(session)
            view_sess.pop('folder_url')
            session_list.append(view_sess)
        LOGGER.info("Sessions sucessfully retrived: [lenght={}]".format(len(session_list)))
        return session_list

    def delete_session(self, session_id):
        """
        Removes a Rumba session.

        This method deletes from the database. Sessions can only be remoced if they have been
        stopped. In order to remove a live session, it is mandatory to remove it first.
        :param session_id: Id of the session to remove.
        :raises:
            - IllegalSessionStateException, if the session does not exist.
            - IlegalSessionStateException, if the session is active.
            - ValueError, if the provided id is not a valid id.
        """
        LOGGER.info("Removing session: [id={}]".format(session_id))
        GenericValidator.validate_id(session_id)
        session = self.get_session(session_id)
        if session['state'] == SessionStatus.ACTIVE.value:
            raise IllegalSessionStateException("Session is active: it should be stopped first.")
        FileSystemService.get_instance().delete_session_directory(band=session['band'])
        RumbaSession.objects(id=session_id).delete()
        LOGGER.info("Session successfully removed: [id={}]".format(session_id))

    def stop_session(self, session_id):
        """
        Stops an active session.

        Stopping a session means that no more users would be able to stream video to the server.
        Of course, only active sessions could be stopped.
        :param session_id: Id of the session to stop.
        :raises:
            - ValueError, if the specified id is not valid.
            - IllegalSessionStateException: If the session was not active.
        """
        LOGGER.info("Stopping session: [id={}]".format(session_id))
        GenericValidator.validate_id(session_id)
        session = self.get_session(session_id)
        valid_states = [SessionStatus.CREATED.value, SessionStatus.ACTIVE.value]
        if session['state'] not in valid_states:
            raise IllegalSessionStateException("Only active and initialized sessions can be stopped.")
        db_session = RumbaSession.objects(id=session_id).first()
        if  session['state'] == SessionStatus.ACTIVE.value:
            LOGGER.info("Stopping audio recording.")
            AudioManager.get_instance().stop_audio()
        db_session.update(set__state=SessionStatus.FINISHED.value)
        LOGGER.info("Session successfully stopped: [id={}]".format(session_id))

    def get_current_session(self):
        """

        :return:
        """
        LOGGER.info("Retrieveing current session")
        states = [SessionStatus.ACTIVE.value, SessionStatus.CREATED.value]
        session = RumbaSession.objects.filter(state__in=states).first()
        if session is None:
            return None
        LOGGER.info("Session sucessfully retrieved: [id={}]".format(session['id']))
        LOGGER.debug("Session information: {}".format(session))
        view_sess = MongoHelper.to_dict(session)
        view_sess.pop('folder_url')
        return view_sess

    def set_session_logo(self, session_id, image_file):
        """

        :param session_id:
        :param image_file:
        :return:
        """
        LOGGER.info("Setting session logo: [session_id={}]".format(session_id))
        try:
            GenericValidator.validate_id(session_id)
            FilesValidator.validate_image_format(image_file)
            session = self.get_session(session_id=session_id)
            FileSystemService.get_instance().save_session_logo(band=session['band'],
                                                               logo=image_file)
            LOGGER.info("Session logo successfully stored: [session_id={}]".format(session_id))
        except Exception as ex:
            LOGGER.exception("Error setting session logo: ")
            raise ex

    def get_session_logo_url(self, session_id):
        """
        Method for retrieving the path where the session logo is stored.
        :param session_id: Id of the session.
        :return: URL containing the FS path where the logo is located.
        :rtype: str
        :raises:
            - SessionValidationException, if the session has no stored logo.
            - ValueError, if provided parameter is not a valid session name.
        """
        LOGGER.info("Getting session logo: [session_id={}]".format(session_id))
        try:
            GenericValidator.validate_id(session_id)
            session = self.get_session(session_id=session_id)
            url = FileSystemService.get_instance().get_session_logo_url(
                band=session['band'])
            LOGGER.info("Session logo URL successfully retrieved.")
            return url
        except Exception as ex:
            LOGGER.exception("Error getting session logo: ")
            raise ex

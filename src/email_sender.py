import os
import sys
import smtplib
import traceback
from datetime import datetime
from email.message import EmailMessage
from socket import gethostname

import config
from src.Logger import LOGGER
try:
    from config import email_config
except ImportError:
    LOGGER.warning("Could not find `email_config.py` in the project root. Please create it if you want to use the "
                   "emailing feature. See `config.py` for more details.")
    email_config = None


CRITICAL_SUBJECT = "[image-anonymisation]: Execution stopped due to uncaught {etype}."
ERROR_SUBJECT = "[image-anonymisation]: Processing error encountered."
FINISHED_SUBJECT = "[image-anonymisation]: Anonymisation finished."


def email_excepthook(etype, ex, tb):
    """
    Function which can be replaced with sys.excepthook in order to send an email when the program exits due to an
    uncaught exception.

    :param etype: Exception type
    :type etype:
    :param ex: Exception instance
    :type ex: BaseException
    :param tb: Traceback object representing the exception's traceback
    :type tb: traceback.traceback
    """
    # Send an email
    send_mail("critical", etype=etype, ex=ex, tb=tb, msg=None)


def send_mail(message_type, etype=None, ex=None, tb=None, msg=None):
    """
    Send an email of type `message_type`. The sender, receiver(s) and smtp-server are configured in `email_config.py`.
    If  `--log-folder` is specified to `src.main`, the log-file will be attached to the message.

    :param message_type: Type of message. This determines the subject and contents of the message. Must be one of

                         - `critical`: This is suitable for critical errors which cause the program to exit abnormally.
                                       A critical message requires `etype`, `ex` and `tb` to be specified, and will
                                       include the exception type in the subject, and the traceback in the contents.
                         - `error`: This message is suitable for processing errors which do not cause the program to
                                    exit.
                         - `finished`: This message type should be used when the program exits normally.

    :type message_type: str
    :param etype: Exception type
    :type etype: type | None
    :param ex: Exception instance
    :type ex: BaseException | None
    :param tb: Traceback object
    :type tb: traceback.traceback | None
    :param msg: Message to include in the contents of the email.
    :type msg: str | None
    """
    # Determine subject
    if message_type == "critical":
        msg = "".join(traceback.format_exception(etype, ex, tb))
        subject = CRITICAL_SUBJECT.format(etype=etype.__name__)
    elif message_type == "error":
        subject = ERROR_SUBJECT
    elif message_type == "finished":
        subject = FINISHED_SUBJECT
    else:
        raise ValueError(f"Function `email.send_mail` got invalid message type: {message_type}")
    # Create the message
    message = create_base_message(subject, msg)
    # Try to send the email. If sending fails, log the message as an error, and continue.
    try:
        with smtplib.SMTP(email_config.smtp_host, email_config.port) as smtp:
            smtp.sendmail(from_addr=email_config.from_address, to_addrs=email_config.to_addresses, msg=message)
    except Exception as err:
        LOGGER.error(__name__, f"Got error '{str(err)}' when attempting to send e-mail.")


def create_base_message(subject, msg=None):
    """
    Create a base-message which is common for all message-types

    :param subject: Message subject
    :type subject: str
    :param msg: Optional message to include in the contents.
    :type msg: str | None
    :return: Properly formatted email message converted to a string.
    :rtype: str
    """
    message = EmailMessage()
    message["From"] = email_config.from_address
    message["To"] = email_config.to_addresses
    message["Subject"] = subject
    message.set_content("\n".join([
        50 * "_",
        f"Hostname: {gethostname()}",
        f"Time: {datetime.now().strftime(config.datetime_format)}",
        f"Log file: {LOGGER.log_file_path}",
        50 * "_",
    ]))
    # Add `msg` to the contents if it is not None
    if msg is not None:
        _append_content(message, msg)
    # Attach the log file if it is available
    if LOGGER.log_file_path is not None:
        _attach_log_file(message)
    return message.as_string()


def _append_content(message, content, sep="\n"):
    """
    Append `content` to `message`'s contents.

    :param message: Message insance
    :type message: EmailMessage
    :param content: Content to append
    :type content: str
    :param sep: Separator between existing and appended content.
    :type sep: str
    """
    new_content = message.get_content() + sep + content
    message.set_content(new_content)


def _attach_log_file(message):
    """
    Attach the LOGGER's log-file to `message`

    :param message: Message instance
    :type message: EmailMessage
    """
    maintype = "text"
    subtype = "plain"
    filename = LOGGER.log_file_path.split(os.sep)[-1]
    with open(LOGGER.log_file_path, "rb") as fp:
        message.add_attachment(fp.read(), maintype=maintype, subtype=subtype, filename=filename)

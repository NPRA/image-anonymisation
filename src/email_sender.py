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
    import email_config
except ImportError:
    raise ImportError("Could not find `email_config.py` in the project root. Please create it if you want to use the "
                      "emailing feature. See `config.py` for more details.")


CRITICAL_SUBJECT = "[image-anonymisation]: Execution stopped due to uncaught {etype}."
ERROR_SUBJECT = "[image-anonymisation]: Processing error encountered."
FINISHED_SUBJECT = "[image-anonymisation]: Anonymisation finished."


def email_excepthook(etype, ex, tb):
    send_mail("critical", etype=etype, ex=ex, tb=tb, msg=None)
    sys.__excepthook__(etype, ex, tb)


def send_mail(message_type, etype=None, ex=None, tb=None, msg=None):
    if message_type == "critical":
        msg = "".join(traceback.format_exception(etype, ex, tb))
        subject = CRITICAL_SUBJECT.format(etype=etype.__name__)
    elif message_type == "error":
        subject = ERROR_SUBJECT
    elif message_type == "finished":
        subject = FINISHED_SUBJECT
    else:
        raise ValueError(f"Function `email.send_mail` got invalid message type: {message_type}")

    message = create_base_message(subject, msg)
    try:
        with smtplib.SMTP(email_config.smtp_host, email_config.port) as smtp:
            smtp.sendmail(from_addr=email_config.from_address, to_addrs=email_config.to_addresses, msg=message)
    except BaseException as err:
        LOGGER.error(__name__, f"Got error {str(err)} when attempting to send e-mail with contents:\n{message}")


def create_base_message(subject, msg):
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
    new_content = message.get_content() + sep + content
    message.set_content(new_content)


def _attach_log_file(message):
    maintype = "text"
    subtype = "plain"
    filename = LOGGER.log_file_path.split(os.sep)[-1]
    with open(LOGGER.log_file_path, "rb") as fp:
        message.add_attachment(fp.read(), maintype=maintype, subtype=subtype, filename=filename)


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO, format=LOGGER.fmt, datefmt=LOGGER.datefmt)
    sys.excepthook = email_excepthook
    
    LOGGER.set_log_file(r"logs\test.log")
    LOGGER.info(__name__, "Here is some information")
    LOGGER.error(__name__, "Error!", email=True)
    raise ValueError("Foobar")

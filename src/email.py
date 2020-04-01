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
    raise ImportError("Could not find `email_config.py` in the project root.")


CRITICAL_SUBJECT = "[image-anonymisation]: Execution stopped due to uncaught {etype}."
ERROR_SUBJECT = "[image-anonymisation]: Processing error encountered."
FINISHED_SUBJECT = "[image-anonymisation]: Anonymisation finished."


def email_excepthook(etype, ex, tb):
    send_mail("critical", etype=etype, ex=ex, tb=tb, msg=None)
    sys.__excepthook__(etype, ex, tb)


def send_mail(message_type, etype=None, ex=None, tb=None, msg=None):
    if message_type == "critical":
        message = create_critical_message(etype, ex, tb)
    elif message_type == "error":
        message = create_error_message(msg)
    elif message_type == "finished":
        message = create_finished_message(msg)
    else:
        raise ValueError(f"Function `email.send_mail` got invalid message type: {message_type}")

    if LOGGER.log_file_path is not None:
        _attach_log_file(message)

    message = message.as_string()

    try:
        with smtplib.SMTP(email_config.smtp_host, email_config.port) as smtp:
            smtp.sendmail(from_addr=email_config.from_address, to_addrs=email_config.to_addresses, msg=message)
    except BaseException as err:
        LOGGER.error(__name__, f"Got error {str(err)} when attempting to send e-mail with contents:\n{message}")


def create_critical_message(etype, ex, tb):
    message = create_base_message(CRITICAL_SUBJECT.format(etype=etype.__name__))
    tb_string = "".join(traceback.format_exception(etype, ex, tb))
    _append_content(message, tb_string)
    return message


def create_error_message(msg):
    message = create_base_message(ERROR_SUBJECT)
    _append_content(message, msg)
    return message


def create_finished_message(msg):
    message = create_base_message(FINISHED_SUBJECT)
    _append_content(message, msg)
    return message


def create_base_message(subject):
    message = EmailMessage()
    message["From"] = email_config.from_address
    message["To"] = email_config.to_addresses
    message["Subject"] = subject
    message.set_content("\n".join([
        50 * "-",
        f"Hostname: {gethostname()}",
        f"Time: {datetime.now().strftime(config.datetime_format)}",
        f"Log file: {LOGGER.log_file_path}",
        50 * "-",
    ]))
    return message


def _append_content(message, content, sep="\n\n"):
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
    raise ValueError("Foobar")

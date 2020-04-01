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
except ImportError as err:
    raise ImportError("Could not find `email_config.py` in the project root.")


def email_excepthook(etype, ex, tb):
    message = create_message(etype, ex, tb)
    with smtplib.SMTP(email_config.smtp_host, email_config.port) as smtp:
        smtp.sendmail(from_addr=email_config.from_address, to_addrs=email_config.to_addresses, msg=message)

    sys.__excepthook__(etype, ex, tb)


def create_message(etype, ex, tb):
    message = EmailMessage()
    message["From"] = email_config.from_address
    message["To"] = email_config.to_addresses
    message["Subject"] = f"[image-anonymisation]: Execution stopped due to uncaught {etype.__name__}."

    tb_string = "".join(traceback.format_exception(etype, ex, tb))

    message.set_content("\n".join([
        f"Exception: {etype.__name__}: {str(ex)}",
        f"Hostname: {gethostname()}",
        f"Time: {datetime.now().strftime(config.datetime_format)}",
        f"Log file: {LOGGER.log_file_path}",
        tb_string
    ]))
    return message.as_string()


if __name__ == '__main__':
    sys.excepthook = email_excepthook
    raise ValueError("Foobar")

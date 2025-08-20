"""
A module for sending email using smtplib.

send_mail reads the From/To mail headers from the following locations,
in order of preference:
From:
    1) send_from argument
    2) MAIL_FROM field of MAIL_CONFIG file
    3) MAIL_FROM environment variable
    4) MAIL_USER field of MAIL_CONFIG file
    5) MAIL_USER environment variable
To:
    1) send_to argument
    2) MAIL_USER field of MAIL_CONFIG file
    3) MAIL_USER environment variable

"""

# python < 3.10
from __future__ import annotations

import json
import os
import smtplib
import sys
from pathlib import Path
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from os.path import basename


__all__ = ["MailConfig", "get_mail_config", "send_mail"]
g_config_file = os.getenv("MAIL_CONFIG")


class MailConfig:
    """A config file with a set of SMTP server credentials as well as an
    optional MAIL_FROM attribute allowing one to change the name or email
    address the mail appears to originate from.

    ### Attributes
    - MAIL_USER : str - (required) User's email
    - MAIL_PASS : str - (required) User's password
    - MAIL_SERVER : str - (required) SMTP server and port as server:port
    - MAIL_FROM : str - An optional attribute to change the 'From:' header
    """

    def __init__(self, user=None, pswd=None, server=None, mail_from=None):
        self.MAIL_USER = user
        self.MAIL_PASS = pswd
        self.MAIL_SERVER = server
        self.MAIL_FROM = mail_from


def get_mail_config(file: str | Path = g_config_file) -> MailConfig:
    """ Try opening the specified JSON config file and reading the three
    required values (MAIL_USER, MAIL_PASS, MAIL_SERVER) from it, as well as
    an optional MAIL_FROM value.  If the file does not exist or if any of the
    values are not set in the file, fall back to reading the value from an
    environment variable of the same name.  If any required values are unset,
    raises an AssertionError.

    ### Parameters
    - file : str
        The file to try reading the config from

    ### Returns
    - A MailConfig object
    """

    config = MailConfig()
    data = {}
    try:
        with open(file) as f:
            data = json.load(f)
    except FileNotFoundError:
        pass

    for key in config.__dict__.keys():
        val = data.get(key)
        if not val:
            val = os.getenv(key, '')
        config.__setattr__(key, val)

    assert all(
        [config.MAIL_USER, config.MAIL_PASS, config.MAIL_SERVER]
    ), f"mail.py : get_mail_config(file={file}) : One or more required values unset, cannot proceed."
    return config


def send_mail(
    subject: str,
    body: str,
    send_to: list = None,
    *,
    send_from: str = None,
    attachments: list = None,
    mail_config: MailConfig = None,
) -> bool:
    """Send an email to the listed recipient(s) with the given attachment(s)
    using (optionally) the specified mail config obtained from a prior call to
    get_mail_config().  If mail_config is None, get_mail_config() will first be
    called with the config file location set in the MAIL_CONFIG environment
    variable.

    ### Positional parameters
    - subject : str
        The subject line of the email
    - body : str
        The body text of the email
    - send_to : list[str]
        A list of email addresses to send to

    ### Keyword parameters
    - send_from : str
        'From:' header
    - attachments : list[str]
        A list of files to send as attachments
    - mail_config : MailConfig
        A MailConfig object returned by a prior call to get_mail_config()

    ### Returns
    - bool
        True if no exceptions occurred, indicating at least one listed
        recipient should receive the message, False otherwise.
    """

    if not mail_config:
        mail_config = get_mail_config(g_config_file)
    assert isinstance(mail_config, MailConfig), "No config provided, abort"
    mail_user = mail_config.MAIL_USER
    mail_pass = mail_config.MAIL_PASS
    mail_server = mail_config.MAIL_SERVER

    # If send_to is left blank, return to sender...
    if not send_to:
        send_to = [mail_user]
    # ... or if a single address is given, listify it
    elif not isinstance(send_to, list):
        send_to = [send_to]

    # If send_from is not set, try the MAIL_FROM field of the mail config
    if not send_from:
        send_from = mail_config.MAIL_FROM
    # And if that's not set, fall back to the MAIL_USER field we got above
    if not send_from:
        send_from = mail_user

    msg = MIMEMultipart()
    msg["From"] = send_from
    msg["To"] = COMMASPACE.join(send_to)
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = subject

    msg.attach(MIMEText(body))

    for file in attachments or []:
        if file:
            with open(file, "rb") as f:
                part = MIMEApplication(f.read(), Name=basename(file))
            part["Content-Disposition"] = f'attachment; filename="{basename(file)}"'
            msg.attach(part)

    try:
        # Per smtplib docs, if no exceptions occurred, at least one recipient
        # should get the mail
        with smtplib.SMTP(mail_server) as smtp:
            smtp.starttls()
            smtp.login(mail_user, mail_pass)
            smtp.sendmail(send_from, send_to, msg.as_string())
        return True
    except Exception as ex:
        print(f"Exception: {ex}", file=sys.stderr)
        return False

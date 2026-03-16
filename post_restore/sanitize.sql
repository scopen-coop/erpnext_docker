UPDATE `tabEmail Domain`
SET
    email_server='greenmail',
    use_ssl=0,
    use_imap=1,
    use_starttls=0,
    incoming_port=3143,
    smtp_server='greenmail',
    smtp_port=3025,
    use_tls=0,
    use_ssl_for_outgoing=0;

UPDATE `tabEmail Account`
SET email_server='greenmail',
    use_ssl=0,
    use_imap=1,
    use_starttls=0,
    incoming_port=3143,
    smtp_server='greenmail',
    smtp_port=3025,
    use_tls=0,
    use_ssl_for_outgoing=0;

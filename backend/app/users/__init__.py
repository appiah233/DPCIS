"""Users domain module boundary.

Future responsibility:
- Store ``application_users`` keyed permanently by Neon Managed Auth ``auth_subject``
  (JWT ``sub``), rather than treating email addresses or phone numbers as identity keys.
- Hold authoritative application ``role`` (``STUDENT`` | ``ADMIN``) and active flags.
"""

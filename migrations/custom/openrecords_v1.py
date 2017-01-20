"""
Migrate data from OpenRecords V1 database.

Usage:
    PYTHONPATH=/.../openrecords_v2_0 python migrations/custom/openrecords_v1.py

"""
import math
import json
import psycopg2.extras

from functools import wraps
from datetime import datetime

from nameparser import HumanName
from business_calendar import Calendar, MO, TU, WE, TH, FR

from app.constants import (
    request_status,
    response_privacy,
    response_type,
    determination_type,
    role_name,
    user_type_auth,
    user_type_request,
    ACKNOWLEDGMENT_DAYS_DUE,
    permission
)
from app.constants.request_date import RELEASE_PUBLIC_DAYS
from app.request.utils import generate_guid
from app.lib import NYCHolidays
from app.lib.user_information import create_mailing_address
from app.lib.date_utils import local_to_utc

SHOW_PROGRESSBAR = True
try:
    import progressbar
    MOCK_PROGRESSBAR = False
except ImportError:
    MOCK_PROGRESSBAR = True

CONN_V1 = psycopg2.connect(database="openrecords_v1", user="vagrant")
CONN_V2 = psycopg2.connect(database="openrecords_v2_0_dev", user="vagrant")
CUR_V1_X = CONN_V1.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
CUR_V1 = CONN_V1.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
CUR_V2 = CONN_V2.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

CAL = Calendar(
    workdays=[MO, TU, WE, TH, FR],
    holidays=[str(key) for key in NYCHolidays(years=[y for y in range(2015, 2019)]).keys()]
)
CHUNKSIZE = 500
DEFAULT_CATEGORY = 'All'
DUE_SOON_DAYS_THRESHOLD = 2
TZ_NY = 'America/New_York'
MIN_DAYS_AFTER_ACKNOWLEDGE = 20

AGENCY_V1_NAME_TO_EIN = {
    # None = no ein yet found
    "Administration for Children's Services": "0067",
    "Board of Correction": "0073",
    "Board of Elections": "0003",
    "Board of Standards and Appeals": "0059",
    "Business Integrity Commission": "0831",
    "City Commission on Human Rights": "0226",
    "Civilian Complaint Review Board": "0054",
    "Civil Service Commission": "0134",
    "Commission to Combat Police Corruption": "032A",
    "Conflicts of Interest Board": "0312",
    "Department for the Aging": "0125",
    "Department of Buildings": "0810",
    "Department of City Planning": "0030",
    "Department of Citywide Administrative Services": "0868",
    "Department of Consumer Affairs": "0866",
    "Department of Correction": "0072",
    "Department of Cultural Affairs": "0126",
    "Department of Design and Construction": "0850",
    "Department of Education": "0040",
    "Department of Environmental Protection": "0826",
    "Department of Finance": "0836",
    "Department of Health and Mental Hygiene": "0816",
    "Department of Homeless Services": "0071",
    "Department of Housing Preservation and Development": "0806",
    "Department of Information Technology and Telecommunications": "0858",
    "Department of Investigation": "0032",
    "Department of Parks and Recreation": "0846",
    "Department of Probation": "0781",
    "Department of Records and Information Services": "0860",
    "Department of Sanitation": "0827",
    "Department of Transportation": "0841",
    "Department of Youth and Community Development": "0260",
    "Design Commission": "002A",
    "Equal Employment Practices Commission": "0113",
    "Financial Information Services Agency": "0127",
    "Housing Recovery Operations": "826A",
    "Human Resources Administration": "0069",
    "Landmarks Preservation Commission": "0136",
    "Law Department": "0025",
    "Loft Board": None,
    "Mayor's Office of Contract Services": "002H",
    "Mayor's Office of Media and Entertainment": "002M",
    "New York City Fire Department": "0057",
    "New York City Housing Authority": "0996",
    "New York City Housing Development Corporation": None,
    "NYC Emergency Management": "0017",  # NYC Office of Emergency Management
    "Office of Administrative Trials and Hearings": "0820",
    "Office of Collective Bargaining": None,
    "Office of Environmental Remediation": "002K",  # Mayor's Office of Environmental Remediation
    "Office of Labor Relations": "0214",  # NYC Office of Labor Relations
    "Office of Long-Term Planning and Sustainability": "002T",
    "Office of Management and Budget": "0019",
    "Office of Payroll Administration": "0131",
    "Office of the Actuary": "0008",  # NYC Office of the Actuary
    "Office of the Chief Medical Examiner": "816A",  # NYC Office of the Chief Medical Examiner
    "Office of the Mayor": "0002",  # Mayor's Office
    "Office of the Special Narcotics Prosecutor": "0906",  # NYC Office of the Special Narcotics Prosecutor
    "Police Department": "0056",
    "Procurement Policy Board": None,
    "School Construction Authority": "0044",
    "Small Business Services": "0801",  # Department of Small Business Services
    "Taxi and Limousine Commission": "0156",
}

PRIVACY = [
    None,
    response_privacy.PRIVATE,
    response_privacy.RELEASE_AND_PRIVATE,
    response_privacy.RELEASE_AND_PUBLIC
]


class MockProgressBar(object):
    """ Mock progressbar.ProgressBar """

    def __init__(self, max_value):
        self.max_value = max_value

    def update(self, num):
        print('{:.0f}% ({} of {})'.format(
            (num / self.max_value) * 100, num, self.max_value))
        print("\x1b[1A\x1b[2K", end='')

    def finish(self):
        print('100% ({0} of {0})'.format(self.max_value))


def transfer(tablename, query):
    def decorator(transfer_func):
        @wraps(transfer_func)
        def wrapped(*args):
            CUR_V1_X.execute(query)
            bar = progressbar.ProgressBar if not MOCK_PROGRESSBAR else MockProgressBar
            bar = bar(max_value=CUR_V1_X.rowcount)
            print(tablename + "...")
            max_init = bar.max_value
            for chunk in range(math.ceil(CUR_V1_X.rowcount / CHUNKSIZE)):
                for i, row in enumerate(CUR_V1_X.fetchmany(CHUNKSIZE)):
                    max_value_shift = transfer_func(*args, row)
                    if max_value_shift:
                        bar.max_value += max_value_shift
                    if SHOW_PROGRESSBAR:
                        bar.update(i + 1 + (chunk * CHUNKSIZE) - (max_init - bar.max_value))
                CONN_V2.commit()
            if SHOW_PROGRESSBAR:
                bar.finish()
            print()

        return wrapped

    return decorator


def _get_due_date(date_submitted, days_until_due):
    return _process_due_date(CAL.addbusdays(date_submitted, days_until_due))


def _process_due_date(due_date):
    date = due_date.replace(hour=17, minute=00, second=00, microsecond=00)
    return local_to_utc(date, TZ_NY)


def _get_compatible_status(request):
    if request.status in [request_status.CLOSED, request_status.OPEN]:
        status = request.status
    else:
        now = datetime.now()
        due_soon_date = CAL.addbusdays(
            now, DUE_SOON_DAYS_THRESHOLD
        ).replace(hour=23, minute=59, second=59)  # the entire day
        if now > request.due_date:
            status = request_status.OVERDUE
        elif due_soon_date >= request.due_date:
            status = request_status.DUE_SOON
        else:
            status = request_status.IN_PROGRESS
    return status


@transfer("Requests", "SELECT * FROM request")
def transfer_requests(request):
    CUR_V1.execute("SELECT name FROM department WHERE id = %s" % request.department_id)

    agency_ein = AGENCY_V1_NAME_TO_EIN[CUR_V1.fetchone().name]

    privacy = {
        "title": bool(request.title_private),
        "agency_description": request.agency_description_due_date is None
    }

    query = ("INSERT INTO requests ("
             "id, "
             "agency_ein, "
             "category, "
             "title, "
             "description, "
             "date_created, "
             "date_submitted, "
             "due_date, "
             "submission, "
             "status, "
             "privacy, "
             "agency_description, "
             "agency_description_release_date) "
             "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")

    CUR_V2.execute(query, (
        request.id,  # id
        agency_ein,  # agency id
        DEFAULT_CATEGORY,  # category
        request.summary,  # title
        request.text,  # description
        local_to_utc(request.date_created, TZ_NY),  # date_created
        local_to_utc(request.date_received, TZ_NY),  # date_submitted
        local_to_utc(request.due_date, TZ_NY),  # due_date
        request.offline_submission_type,  # submission
        _get_compatible_status(request),  # status
        json.dumps(privacy),  # privacy
        request.agency_description,  # agency_description
        request.agency_description_due_date  # agency_description_release_date
    ))


def _create_response(child, type_, release_date, privacy=None, date_created=None):
    query = ("INSERT INTO responses ("
             "request_id, "
             "privacy, "
             "date_modified, "
             "release_date, "
             "deleted, "
             '"type", '
             "is_editable) "
             "VALUES (%s, %s, %s, %s, %s, %s, %s)")

    if date_created is None:
        date_created = child.date_created

    date_created_utc = local_to_utc(date_created, TZ_NY)

    try:
        request_id = child.request_id
    except AttributeError:
        assert 'FOIL' in child.id
        request_id = child.id

    CUR_V2.execute(query, (
        request_id,  # request_id
        privacy or PRIVACY[child.privacy],  # privacy
        date_created_utc,  # date_modified
        release_date,  # release_date
        False,  # deleted
        type_,  # type
        True  # is_editable
    ))

    CONN_V2.commit()

    CUR_V2.execute("SELECT LASTVAL()")
    return CUR_V2.fetchone().lastval


def _get_release_date(start_date):
    release_date = CAL.addbusdays(start_date, RELEASE_PUBLIC_DAYS)
    return local_to_utc(release_date, TZ_NY)


def _get_note_release_date(note):
    if PRIVACY[note.privacy] == response_privacy.RELEASE_AND_PUBLIC:
        _get_release_date(note.created)
    return None


@transfer("Notes", "SELECT * FROM note WHERE text NOT LIKE '%Request extended:%' AND text NOT LIKE '{%}'")
def transfer_notes(note):
    response_id = _create_response(note, response_type.NOTE,
                                   _get_note_release_date(note))

    query = ("INSERT INTO notes ("
             "id, "
             "content) "
             "VALUES (%s, %s)")

    CUR_V2.execute(query, (
        response_id,  # id
        note.text  # content
    ))


@transfer("Denials",
          "SELECT * "
          "FROM note "
          "WHERE request_id IN ("
          "  SELECT DISTINCT id"
          "  FROM request"
          "  WHERE status = 'Closed'"
          "        AND id NOT IN (SELECT request_id"
          "                       FROM email_notification"
          "                       WHERE subject LIKE '%Acknowledge%')"
          "        AND id NOT IN (SELECT id"
          "                       FROM request"
          "                       WHERE status != 'Open'"
          "                             AND NOT (status = 'Closed' AND prev_status = 'Open')))")
def transfer_denials(note):
    response_id = _create_response(note, response_type.DETERMINATION,
                                   _get_release_date(note.date_created),
                                   privacy=response_privacy.RELEASE_AND_PUBLIC)

    query = ("INSERT INTO determinations ("
             "id, "
             "dtype, "
             "reason) "
             "VALUES (%s, %s, %s)")

    CUR_V2.execute(query, (
        response_id,
        determination_type.DENIAL,
        note.text.lstrip('{"').rstrip('"}').replace('","', '|')
    ))


@transfer("Closings",
          "SELECT * "
          "FROM note "
          "WHERE request_id NOT IN ("
          "  SELECT DISTINCT id"
          "  FROM request"
          "  WHERE status = 'Closed'"
          "        AND id NOT IN (SELECT request_id"
          "                       FROM email_notification"
          "                       WHERE subject LIKE '%Acknowledge%')"
          "        AND id NOT IN (SELECT id"
          "                       FROM request"
          "                       WHERE status != 'Open'"
          "                             AND NOT (status = 'Closed' AND prev_status = 'Open')))"
          "      AND text LIKE '{%}'")
def transfer_closings(note):
    response_id = _create_response(note, response_type.DETERMINATION,
                                   _get_release_date(note.date_created),
                                   privacy=response_privacy.RELEASE_AND_PUBLIC)

    query = ("INSERT INTO determinations ("
             "id, "
             "dtype, "
             "reason) "
             "VALUES (%s, %s, %s)")

    reason = note.text.lstrip('{"').rstrip('"}').replace('","', '|')
    if reason == '':
        reason = 'No reasons for closing provided.'

    CUR_V2.execute(query, (
        response_id,
        determination_type.CLOSING,
        reason
    ))


@transfer("Acknowledgments (from `email`)",
          "SELECT DISTINCT ON (request_id) * "
          "FROM email_notification "
          "WHERE subject LIKE '%Acknowledged%'")
def transfer_acknowledgments_from_email(email):
    response_id = _create_response(email, response_type.DETERMINATION,
                                   _get_release_date(email.time_sent),
                                   privacy=response_privacy.RELEASE_AND_PUBLIC,
                                   date_created=email.time_sent)

    query = ("INSERT INTO determinations ("
             "id, "
             "dtype, "
             '"date") '
             "VALUES (%s, %s, %s)")

    CUR_V1.execute("SELECT email_content "
                   "FROM email_notification "
                   "WHERE request_id = '{}' "
                   "      AND subject LIKE '%FOIL Request Submitted%'".format(email.request_id))
    result = CUR_V1.fetchone()
    if result is not None:
        original_due_date = datetime.strptime(result.email_content['due_date'], '%Y-%m-%d')
    else:
        CUR_V1.execute("SELECT date_received FROM request WHERE id = '%s'" % email.request_id)
        original_due_date = CAL.addbusdays(CUR_V1.fetchone().date_received, ACKNOWLEDGMENT_DAYS_DUE)
    date = _get_due_date(
        original_due_date,
        int(email.email_content['acknowledge_status'].rstrip(" days"))
    )
    CUR_V2.execute(query, (
        response_id,
        determination_type.ACKNOWLEDGMENT,
        date
    ))


@transfer("Acknowledgments (from `request`)",
          "SELECT * "
          "FROM request "
          "WHERE id NOT IN (SELECT request_id"
          "                 FROM email_notification"
          "                 WHERE subject LIKE '%Acknowledged%')"
          "      AND status != 'Open'"
          "      AND NOT (status = 'Closed' AND prev_status = 'Open')")
def transfer_acknowledgments_from_request(request):
    """
    Any request (excluding those for which an acknowledgment can been
    found via email notification) without an 'Open' status and
    without a previous status of 'Open' if its current status is 'Closed',
    is considered to have been, at some point, acknowledged.

    For a request that...
                                responses.date_modified     acknowledgments.date
    ...has NOT been extended:   request.date_received       request.due_date
    ...has been extended:       request.date_received       date_received + 5 + 20 (minimum)

    """
    # get dates
    date_created = request.date_received
    if not request.extended:
        final_due_date = request.due_date
        date = _process_due_date(final_due_date)
    else:
        original_due_date = CAL.addbusdays(request.date_received, ACKNOWLEDGMENT_DAYS_DUE)
        date = _get_due_date(
            original_due_date,
            MIN_DAYS_AFTER_ACKNOWLEDGE
        )

    response_id = _create_response(request, response_type.DETERMINATION,
                                   _get_release_date(date_created),
                                   privacy=response_privacy.RELEASE_AND_PUBLIC,
                                   date_created=date_created)

    query = ("INSERT INTO determinations ("
             "id, "
             "dtype, "
             '"date") '
             "VALUES (%s, %s, %s)")

    CUR_V2.execute(query, (
        response_id,
        determination_type.ACKNOWLEDGMENT,
        date
    ))


# TODO: Re-Openings before 6/13/2016 cannot be found
@transfer("Re-Openings", "SELECT * FROM email_notification WHERE subject LIKE '%reopened%'")
def transfer_reopenings(email):
    response_id = _create_response(email, response_type.DETERMINATION,
                                   _get_release_date(email.time_sent),
                                   privacy=response_privacy.RELEASE_AND_PUBLIC,
                                   date_created=email.time_sent)

    query = ("INSERT INTO determinations ("
             "id, "
             "dtype, "
             '"date") '
             "VALUES (%s, %s, %s)")

    CUR_V1.execute("SELECT due_date FROM request WHERE id = '%s'" % email.request_id)
    due_date = CUR_V1.fetchone().due_date
    date = local_to_utc(due_date, TZ_NY)

    CUR_V2.execute(query, (
        response_id,
        determination_type.ACKNOWLEDGMENT,
        date
    ))


@transfer('Extensions (from `email`)', "SELECT * FROM email_notification WHERE subject LIKE '%Extension%'")
def transfer_extensions_from_email(email):
    response_id = _create_response(email, response_type.DETERMINATION,
                                   _get_release_date(email.time_sent),
                                   privacy=response_privacy.RELEASE_AND_PUBLIC,
                                   date_created=email.time_sent)

    query = ("INSERT INTO determinations ("
             "id, "
             "dtype, "
             '"date") '
             "VALUES (%s, %s, %s)")

    date = email.email_content['due_date']
    if email.email_content['days_after'] == -1:  # if custom
        date = datetime.strptime(date, '%m/%d/%Y')
    else:
        date = datetime.strptime(date, '%Y-%m-%d')
    date = _process_due_date(date)

    CUR_V2.execute(query, (
        response_id,
        determination_type.EXTENSION,
        date
    ))


# TODO: manual extensions for notes with null `due_date` and `days_after`
@transfer('Extensions (from `note`)',
          "SELECT * "
          "FROM note "
          "WHERE text LIKE 'Request extended:%' "
          "      AND date_created < '2016-06-13' "  # date email notifications for responses began
          "      AND due_date IS NOT NULL "
          "      AND days_after IS NOT NULL")
def transfer_extensions_from_note(note):
    response_id = _create_response(note, response_type.DETERMINATION,
                                   _get_release_date(note.date_created),
                                   privacy=response_privacy.RELEASE_AND_PUBLIC,
                                   date_created=note.date_created)

    query = ("INSERT INTO determinations ("
             "id, "
             "dtype, "
             '"date") '
             "VALUES (%s, %s, %s)")

    CUR_V2.execute(query, (
        response_id,
        determination_type.EXTENSION,
        CAL.addbusdays(note.due_date, note.days_after)
    ))


def _get_record_release_date(record):
    if PRIVACY[record.privacy] == response_privacy.RELEASE_AND_PUBLIC:
        if record.release_date is not None:
            release_date = record.release_date
        else:
            release_date = CAL.addbusdays(record.date_created, RELEASE_PUBLIC_DAYS)
        return local_to_utc(release_date, TZ_NY)
    return None


@transfer('Files', "SELECT * FROM record WHERE filename IS NOT NULL AND filename != ''")
def transfer_files(record):
    response_id = _create_response(record, response_type.FILE,
                                   _get_record_release_date(record))

    # TODO: in script that transfers files, update files table (mime type, size, hash)
    query = ("INSERT INTO files ("
             "id, "
             "title, "
             '"name") '
             "VALUES (%s, %s, %s)")

    if record.description is None or record.description.strip() == '':
        title = record.filename
    else:
        title = record.description

    CUR_V2.execute(query, (
        response_id,
        title,
        record.filename
    ))


@transfer('Links', "SELECT * FROM record WHERE url IS NOT NULL and url != '1'")
def transfer_links(record):
    response_id = _create_response(record, response_type.LINK,
                                   _get_record_release_date(record))

    query = ("INSERT INTO links ("
             "id, "
             "title, "
             "url) "
             "VALUES (%s, %s, %s)")

    CUR_V2.execute(query, (
        response_id,
        record.description,
        record.url
    ))


@transfer('Instructions', "SELECT * FROM record WHERE access IS NOT NULL")
def transfer_instructions(record):
    response_id = _create_response(record, response_type.INSTRUCTIONS,
                                   _get_record_release_date(record))

    query = ("INSERT INTO instructions ("
             "id, "
             "content) "
             "VALUES (%s, %s)")

    if record.description is None or record.description.strip() == '':
        content = record.access
    else:
        content = ':\n\n'.join((record.description, record.access))

    CUR_V2.execute(query, (
        response_id,
        content
    ))


# TODO: Handle emails where recipient does not have an email address?
@transfer('Emails', "SELECT * "
                    "FROM email_notification "
                    "WHERE recipient NOT IN (SELECT id "
                    "                        FROM public.user "
                    "                        WHERE email is NULL)")
def transfer_emails(email):
    response_id = _create_response(email, response_type.EMAIL,
                                   release_date=None,
                                   privacy=response_privacy.PRIVATE,
                                   date_created=email.time_sent)

    query = ("INSERT INTO emails ("
             "id, "
             '"to", '
             "subject, "
             "body) "
             "VALUES (%s, %s, %s, %s)")

    CUR_V1.execute("SELECT email FROM public.user WHERE id = %s"
                   % email.recipient)
    to = CUR_V1.fetchone().email

    CUR_V2.execute(query, (
        response_id,
        to,
        email.subject,
        email.email_content.get('email_text')
    ))


@transfer('Users', "SELECT * FROM public.user "
                   "WHERE alias NOT IN (SELECT name FROM department) "
                   "      AND alias IS NOT NULL "
                   "      OR (first_name IS NOT NULL "
                   "          AND last_name IS NOT NULL)")
def transfer_users(user_ids_to_guids, user):
    # get agency_ein and auth_user_type
    auth_user_type = user_type_auth.AGENCY_LDAP_USER
    is_active = False
    if user.department_id:
        CUR_V1.execute("SELECT name FROM department WHERE id = %s" % user.department_id)
        agency_ein = AGENCY_V1_NAME_TO_EIN[CUR_V1.fetchone().name]
        is_active = True
    else:
        agency_ein = None
        auth_user_type = user_type_auth.ANONYMOUS_USER

    mailing_address = create_mailing_address(
        user.address1,
        user.city,
        user.state,
        user.zipcode,
        user.address2
    )

    name = HumanName(user.alias)  # alias assumed never none

    guid = generate_guid()
    user_ids_to_guids[user.id] = guid

    query = ("INSERT INTO users ("
             "guid, "
             "auth_user_type, "
             "agency_ein, "
             "is_super, "
             "is_agency_active, "
             "is_agency_admin, "
             "first_name, "
             "middle_initial, "
             "last_name, "
             "email, "
             "email_validated, "
             "terms_of_use_accepted, "
             "title, "
             "organization, "
             "phone_number, "
             "fax_number, "
             "mailing_address) "
             "VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")

    CUR_V2.execute(query, (
        guid,  # guid
        auth_user_type,  # auth_user_type
        agency_ein,  # agency_ein
        False,  # is_super
        user.is_staff,  # is_agency_active
        user.role == role_name.AGENCY_ADMIN,  # is_agency_admin
        name.first.title().strip(),  # first_name
        name.middle[0].upper() if name.middle else None,  # middle_initial
        name.last.title().strip(),  # last_name
        user.email,  # email
        is_active,  # email_validated
        is_active,  # terms_of_user_accepted
        None,  # title
        None,  # organization
        user.phone if user.phone != 'None' else None,  # phone_number
        user.fax if user.fax != 'None' else None,  # fax_number
        json.dumps(mailing_address)  # mailing_address
    ))


@transfer("User Requests (Assigned Users)", "SELECT * FROM owner WHERE active is TRUE")
def transfer_user_requests_assigned_users(user_ids_to_guids, owner):
    if owner.user_id in user_ids_to_guids:  # bar count will be greater than what is transferred

        CUR_V2.execute("SELECT permissions FROM roles WHERE name = '%s'" %
                       (role_name.AGENCY_ADMIN if owner.is_point_person
                        else role_name.AGENCY_OFFICER))

        query = ("INSERT INTO user_requests ("
                 "user_guid, "
                 "auth_user_type, "
                 "request_id, "
                 "request_user_type, "
                 "permissions) "
                 "VALUES (%s, %s, %s, %s, %s)")

        CUR_V2.execute(query, (
            user_ids_to_guids[owner.user_id],
            user_type_auth.AGENCY_LDAP_USER,
            owner.request_id,
            user_type_request.AGENCY,
            CUR_V2.fetchone().permissions
        ))


@transfer("User Requests (Requesters)", "SELECT * FROM request")
def transfer_user_requests_requesters(user_ids_to_guids, request):
    CUR_V1.execute("SELECT user_id FROM subscriber WHERE request_id = '%s'" % request.id)

    user_id = None
    for subscriber in CUR_V1.fetchall():
        if subscriber.user_id in user_ids_to_guids:
            user_id = subscriber.user_id
            break  # just one requester

    query = ("INSERT INTO user_requests ("
             "user_guid, "
             "auth_user_type, "
             "request_id, "
             "request_user_type, "
             "permissions) "
             "VALUES (%s, %s, %s, %s, %s)")

    CUR_V2.execute(query, (
        user_ids_to_guids[user_id],
        user_type_auth.ANONYMOUS_USER,
        request.id,
        user_type_request.REQUESTER,
        permission.NONE
    ))


def assign_admins():
    """
    Assign every agency admin to their agency's requests if
    they have not been assigned already.

    Why would there be agencies with unassigned admins?
        In V1, special users that represented agencies as a whole
        would be automatically assigned. V2 no longer handles assigning
        these types of users so they are never transferred.
    """
    print("Assigning Administrators...")
    CUR_V2.execute("SELECT permissions FROM roles WHERE name = '%s'" % role_name.AGENCY_ADMIN)
    admin_permissions = CUR_V2.fetchone().permissions

    CUR_V2.execute("SELECT * "
                   "FROM users "
                   "WHERE is_agency_active IS TRUE "
                   "      AND is_agency_admin IS TRUE")

    for user in CUR_V2.fetchall():
        user_name = "{} {}{}".format(
            user.first_name,
            user.middle_initial + '. ' if user.middle_initial else '',
            user.last_name
        )
        CUR_V2.execute("SELECT * FROM requests WHERE agency_ein = '%s'" % user.agency_ein)
        print("Found {} requests for {}. Assigned to... ".format(CUR_V2.rowcount, user_name), end='')
        num_assigned = 0
        for request in CUR_V2.fetchall():
            CUR_V2.execute("SELECT COUNT(*) "
                           "FROM user_requests "
                           "WHERE request_id = %s "
                           "      AND user_guid = %s "
                           "      AND auth_user_type = %s",
                           (request.id, user.guid, user.auth_user_type))
            if CUR_V2.fetchone().count == 0:
                # user has not been assigned to this request
                CUR_V2.execute("INSERT INTO user_requests ("
                               "user_guid, "
                               "auth_user_type, "
                               "request_id, "
                               "request_user_type, "
                               "permissions) "
                               "VALUES (%s, %s, %s, %s, %s)",
                               (user.guid,
                                user.auth_user_type,
                                request.id,
                                user_type_request.AGENCY,
                                admin_permissions))
                num_assigned += 1
        CONN_V2.commit()
        print(num_assigned)


def transfer_all():
    transfer_requests()

    user_ids_to_guids = {}
    transfer_users(user_ids_to_guids)
    transfer_user_requests_assigned_users(user_ids_to_guids)
    transfer_user_requests_requesters(user_ids_to_guids)

    # Responses
    transfer_notes()
    transfer_files()
    transfer_links()
    transfer_instructions()
    transfer_emails()
    # Responses: Determinations
    transfer_denials()
    transfer_closings()
    transfer_acknowledgments_from_email()
    transfer_acknowledgments_from_request()
    transfer_reopenings()
    transfer_extensions_from_note()
    transfer_extensions_from_email()


if __name__ == "__main__":
    transfer_all()
    assign_admins()

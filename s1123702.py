import json
import datetime
import email.utils
from tld import get_fld, get_tld, get_tld_names

def read_json_file(filepath: str) -> list[dict]:
    with open(filepath, 'r') as json_file:
        return json.load(json_file)

accept_list = read_json_file('zalando.nl_accept.har')['log']['entries']
reject_list = read_json_file('zalando.nl_reject.har')['log']['entries']
domain_map = read_json_file('domain_map.json')

def entry_has_header(entry: dict, entry_component: str, header_name: str) -> bool:
    valid_entry_components = ('request', 'response')
    if entry_component not in valid_entry_components:
        raise RuntimeError(f'attr \'entry_component\' must be one of {valid_entry_components}')
    
    for header in entry[entry_component]['headers']:
        if header.get('name') == header_name:
            return True
    return False


def is_third_party( entry: dict, first_party_domain: str) -> bool:
    return first_party_domain != get_fld(entry['request'].get('url'))


def is_age_greater_than(cookie: str, min_age_in_days: int) -> bool:
    cookie_attrs = {x[0]: x[1] if(len(x) == 2) else x[0] for x in map(lambda x: x.strip().lower().split('='), cookie.split(';'))}
    
    if datetime.timedelta(seconds=int(cookie_attrs.get('max-age',0))).days >= min_age_in_days:
        return True
    
    # In order for this script to keep working in the future, we'll compare the expiration date of the cookie 
    # to the date when the data was collected, instead of comparing it with `datetime.datetime.today()
    date_of_collection = datetime.datetime(year=2024, month=2, day=28,tzinfo=datetime.timezone.utc)
    expiration_date = email.utils.parsedate_to_datetime(cookie_attrs.get('expires'))
    
    if (expiration_date - date_of_collection).days >= min_age_in_days:
        return True
    
    return False
    

def has_tracking_cookies(entry: dict):
    for header in entry['response']['headers']:
        if header.get('name') == 'set-cookie' and 'samesite=none' in header.get('value').lower() and is_age_greater_than(header.get('value'), 60):
            return True
    return False


def map_entry_to_fld(entry: dict) -> str:
    return get_fld(entry['request'].get('url'))


def map_entry_to_tld(entry: dict) -> str:
    return get_tld(entry['request'].get('url'))


def map_entry_to_entity_name(entry: dict) -> str:
    entry_fld = map_entry_to_fld(entry)
    entity_dict = domain_map.get(entry_fld)

    # In my HAR file I found a URL that yielded a wrong fld, when I used `get_tld()` instead of `get_fld()`
    # I got the correct match for the entity name. In principle, using the `get_tld()` method should not
    # be a problem, since that in the cases where it returns `co.uk` for instance, it will not match with
    # any entry in the domain_map file
    if entity_dict == None:
        entity_dict = domain_map.get(map_entry_to_tld(entry))

    return entity_dict.get('entityName', 'unknown')


def map_entry_to_summary_dict(entry: dict, first_party_domain: str) -> dict:
    summary_dict = {}
    url = entry['request'].get('url')
    summary_dict['url_first_128_char'] = url[:128] if len(url) > 128 else url
    summary_dict['url_domain'] = get_fld(url)
    summary_dict['is_third_party'] = is_third_party(entry, first_party_domain)
    summary_dict['set_http_cookies'] = entry_has_header(entry, 'response', 'set-cookie')
    summary_dict['entity_name'] = map_entry_to_entity_name(entry)

    return summary_dict
    
def produce_dict(har_content: list[dict], first_party_domain: str) -> dict:
    result_dict = {}
    result_dict['num_reqs'] = len(har_content)
    result_dict['num_requests_w_cookies'] = len(list(filter(lambda entry: entry_has_header(entry, 'request', 'cookie'), har_content)))
    result_dict['num_responses_w_cookies'] = len(list(filter(lambda entry: entry_has_header(entry, 'response', 'set-cookie'), har_content)))
    result_dict['third_party_domains'] = list(set(map(map_entry_to_fld, filter(lambda entry: is_third_party(entry, first_party_domain), har_content))))
    result_dict['tracker_cookie_domains'] = list(set(map(map_entry_to_fld, filter(has_tracking_cookies, har_content))))
    result_dict['third_party_entities'] = list(set(map(map_entry_to_entity_name, har_content)))
    result_dict['requests'] = list(map(lambda entry: map_entry_to_summary_dict(entry, first_party_domain), har_content))
    return result_dict

def main():
    accept_dict = produce_dict(accept_list, 'zalando.nl')
    reject_dict = produce_dict(reject_list, 'zalando.nl')

if __name__ == '__main__':
    main()

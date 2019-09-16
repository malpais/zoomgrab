#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys
import re
import math
import cfscrape
import click
from bs4 import BeautifulSoup
from output_handler import OutputHandler

proxies = {
    # 'http': 'http://127.0.0.1:8080',
    # 'https': 'http://127.0.0.1:8080',
}

"""
ZoomScraper - A wrapper class to use cfscrape

In order to mitigate cloudflare's anti-bot protection, the cfscrape
library uses node to trick cloudflare into thinking it's a js-enabled
browser. The library sits on top of the requests library, except it 
manages cloudflare tokens and cookies intelligently. 

This class wraps the cfscrape functionality so the script can make
multiple requests but use the original cookies provided by cloudflare
to maintain an authorized session.

The `delay` parameter is the amount of time cfscrape will delay the next
request should cloudflare return an HTTP 429 (throttled) error. Setting it
too low may result in many failed requests due to the lack of time between
requests. 10 seconds has been pretty reliable in testing.
"""
class ZoomScraper():
    url = ''
    scraper = None
    tokens = {}
    user_agent = ''
    domain = ''
    username_format = 'full'
    pages = []
    page_count = 1
    current_page = None
    output_dir = None
    output_format = None
    output_handler = None


    """
    Instantiate ZoomScraper

    param: url - URL of target
    
    Initializes a cfscrape scraper object and performs an initial GET request
    to the target URL to acquire cloudflare-specific tokens for future use
    """
    def __init__(self, url, output_dir=None, output_format=None, username_format='full', domain='', gophish_url=None, gophish_api_key=None):
        self.url = url
        self.scraper = cfscrape.create_scraper(delay=10)
        try:
            self.tokens, self.user_agent = cfscrape.get_tokens(url, proxies=proxies, verify=False)
        except Exception as e:
            click.secho(f'[!] failed to retrieve scrape page, received HTTP {str(e)}... exiting.', fg='red')
            sys.exit(-1)
        self.output_dir = output_dir
        self.output_format = output_format
        self.username_format = username_format
        self.domain = domain
        self.output_handler = OutputHandler(output_dir, domain, username_format, output_format, gophish_url, gophish_api_key)

    """
    Scrape page at URL

    param url: URL of target (optional)

    Performs a GET of an initialized URL or a new URL from the user. Cloudflare
    tokens retrieved in __init__() are re-used during scraping. Finally, parse 
    any scraped HTML with BeautifulSoup and return the bs4 object.
    """
    def scrape(self, url='', store_pagecount=False):
        if not url:
            url = self.url

        response = self.scraper.get(url, cookies=self.tokens, proxies=proxies, verify=False)
        if response.status_code != 200:
            click.secho(f'[!] failed to retrieve scrape page, received HTTP {response.status_code}... exiting.', fg='red')
            sys.exit(-1)
        self.current_page = BeautifulSoup(response.content, 'html.parser')
        if store_pagecount:
            self._get_pagecount(self.current_page)
            click.secho(f'[+] scraping page 1/{self.page_count}...', fg='green')

        # Extract data from scraped page and save results if requested.
        person_results = self._get_data_from_page(self.username_format, self.domain)
        self.output_handler._save_results(person_results)


    """
    Loops through the total number of zoom pages and scrape()-s employee data. Will print
    results to stdout upon completion.
    """
    def scrape_pages(self):
        for page in [f'{self.url}?pageNum={x}' for x in range(2, self.page_count + 1)]:
            click.secho(f'[+] scraping page {page.split("=")[-1]}/{self.page_count}...', fg='green')
            self.scrape(page)
        self.output_handler._print_results()
        if self.output_handler.gophish_api:
            self.output_handler._import_into_gophish()


    """
    Determine result counts from Zoominfo

    param page_content: BeautifulSoup page object of a zoom result

    return int: Total contacts found across a count of zoom pages
    """
    def _get_pagecount(self, page_content):
        # Regex to match the counter text in the first page of results
        zoom_total_contacts_pattern = re.compile(r'(?P<num_contacts>\d+) results')
        total_search_pages = page_content.find('h2', {
            'class': 'page_searchResults_numberOfResults',
        })
        # Matches section of page that shows number of total results
        # "1-25 of 1,742 Contacts"
        # Replace commas to get a number value for number of contacts
        zoom_total_contacts = zoom_total_contacts_pattern.search(total_search_pages.text.replace(',','')).group('num_contacts')
        zoom_page_count = math.ceil(int(zoom_total_contacts) / 25)

        click.secho(f'[+] found {zoom_total_contacts} records across {zoom_page_count} pages of results...', fg='green')
        click.secho(f'[+] starting scrape of {zoom_page_count} pages. scraping cloudflare sites can be tricky, be patient!', fg='green')

        self.page_count = zoom_page_count


    """
    Convert HTML into person data

    param row_element: BeautifulSoup row object containing person data
    param email_format_string: User-provided string to determine the output format of parsed username
    param domain: User-provided string to append to converted username data

    return dict: Dictionary value of parsed person data from HTML row.
    """
    def _parse_employee_info(self, row_element, email_format_string='', domain=''):
        # Find relevent elements for personnel data in bs4 row object
        name_selector = row_element.find('div', {'class': 'tableRow_personName'})
        title_selector = row_element.find('div', {'class': 'dynamicLink'})
        location_selector = row_element.findAll('a', {'class': 'dynamicLink'})

        # Pull text values for data if available, falling back to defaults if not exists
        person_name = name_selector.text if name_selector else None
        person_title = title_selector.text if title_selector else ''
        person_location = ', '.join([field.text for field in location_selector]) if location_selector else 'Unknown'
        username = ''

        if person_name:
            # Split up a name into parts for parsing, trimming special characters
            # 
            # 'Joe Z. Dirt' -> ['Joe', 'Z', 'Dirt']
            # 'Mary Skinner' -> ['Mary', 'Skinner']
            name_parts = person_name.replace('.', '').replace('\'','').split(' ')

            # Switch on `email_format_string` to chop up name_parts
            # based on user-defined format string. Special care given
            # to names with middle names.
            if email_format_string == 'firstlast':
                username = f'{name_parts[0]}{name_parts[-1]}'
            elif email_format_string == 'firstmlast':
                if len(name_parts) > 2:
                    username = f'{name_parts[0]}{name_parts[1][:1]}{name_parts[-1]}'
                else:
                    username = f'{name_parts[0]}{name_parts[-1]}'
            elif email_format_string == 'flast':
                username = f'{name_parts[0][:1]}{name_parts[-1]}'
            elif email_format_string == 'lastf':
                username = f'{name_parts[-1]}{name_parts[0][:1]}'
            elif email_format_string == 'first.last':
                username = f'{name_parts[0]}.{name_parts[-1]}'
            elif email_format_string == 'first_last':
                username = f'{name_parts[0]}_{name_parts[-1]}'
            elif email_format_string == 'fmlast':
                if len(name_parts) > 2:
                    username = f'{name_parts[0][:1]}{name_parts[1][:1]}{name_parts[-1]}'
                else:
                    username = f'{name_parts[0][:1]}{name_parts[-1]}'
            else:
                # default to 'full'
                username = ''.join(name_parts)
        return {
            'Full Name': person_name,
            'Title': person_title,
            'Location': person_location,
            'Email': f'{username.lower()}@{domain}',
        }


    """
    Iterate through a scraped page and extract employee data from the HTML

    param username_format: Which format should zoomgrab format the employee email addresses, specified in cli options
    param domain: Domain to use for the generated employee email addresses

    return list: List of parsed employee data
    """
    def _get_data_from_page(self, username_format, domain):
        person_results = []
        for row in self.current_page.findAll('tr', {'class': 'tableRow'})[1:]:
            person_results.append(self._parse_employee_info(row, username_format, domain))
        return person_results


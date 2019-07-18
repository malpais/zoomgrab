#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import re
import os
import sys
import math
import argparse
import json
import csv
import requests
from bs4 import BeautifulSoup
import cfscrape
import click

requests.packages.urllib3.disable_warnings()

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36',
}

proxies = {
    # 'http': 'http://127.0.0.1:8080',
    # 'https': 'http://127.0.0.1:8080',
}

banner = """
███████╗ ██████╗  ██████╗ ███╗   ███╗ ██████╗ ██████╗  █████╗ ██████╗ 
╚══███╔╝██╔═══██╗██╔═══██╗████╗ ████║██╔════╝ ██╔══██╗██╔══██╗██╔══██╗
  ███╔╝ ██║   ██║██║   ██║██╔████╔██║██║  ███╗██████╔╝███████║██████╔╝
 ███╔╝  ██║   ██║██║   ██║██║╚██╔╝██║██║   ██║██╔══██╗██╔══██║██╔══██╗
███████╗╚██████╔╝╚██████╔╝██║ ╚═╝ ██║╚██████╔╝██║  ██║██║  ██║██████╔╝
╚══════╝ ╚═════╝  ╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ 

An OSINT tool designed to scrape employee data from zoominfo.com. 
Results may be delayed due to bypassing Cloudflare's anti-bot protection.

Author: Steve Coward (steve_coward@rapid7.com)
"""

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
    def __init__(self, url, output_dir=None, output_format=None, username_format='full', domain=''):
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
        self.output_handler = OutputHandler(output_dir, domain, username_format, output_format)

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


    """
    Determine result counts from Zoominfo

    param page_content: BeautifulSoup page object of a zoom result

    return int: Total contacts found across a count of zoom pages
    """
    def _get_pagecount(self, page_content):
        # Regex to match the counter text in the first page of results
        zoom_total_contacts_pattern = re.compile(r'(?P<num_contacts>\d+) Contacts')
        total_search_pages = page_content.find('h2', {
            'class': 'page_numberOfResults_header',
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


"""
OutputHandler - Consolidating any output-related functionality under a single class

If the user wants to save search results to disk, zoomgrab will perform some checks
and act appropriately if directories are missing. Depending on the user's preferred
`output_format`, the OutputHandler object will write the results using that format.
"""
class OutputHandler():
    target_domain = ''
    directory = None
    output_format = None
    output_path = ''
    username_format = 'full'
    results = []
    all_results = []
    csv_field_names = ['Email', 'Full Name', 'Title', 'Location']

    def __init__(self, directory, target_domain, username_format, output_format):
        self.directory = directory
        self.target_domain = target_domain
        self.username_format = username_format
        self.output_format = output_format

        if self.directory and self.output_format:
            # If the output directory doesn't exist then create it
            if not os.path.exists(self.directory):
                os.mkdir(self.directory)

            self.output_path = f'{self.directory}/{self.target_domain}-{self.username_format}'

            # if the user wants to store results as a csv, write the csv header first
            if self.output_format == 'csv':
                self._write_csv_header()


    """
    Saves results to the user-specified output format

    param results: list of employee profile data to be saved
    """
    def _save_results(self, results):
        self.results = results
        self.all_results += results
        if self.directory and self.output_format:
            if self.output_format == 'flat':
                self._write_flat()
            elif self.output_format == 'csv':
                self._write_csv()
            elif self.output_format == 'json':
                self._write_json()


    """
    Print all results to stdout
    """
    def _print_results(self):
        for person in self.all_results:
            click.echo(f'[*] {person["Email"]}|{person["Full Name"]}|{person["Title"]}|{person["Location"]}')


    """
    Write results to a flat text file
    """
    def _write_flat(self):
        with open(f'{self.output_path}.txt', 'a') as fh:
            for person in self.results:
                fh.write(f'{person["Email"]}|{person["Full Name"]}|{person["Title"]}|{person["Location"]}\n')


    """
    Write csv header to disk
    """
    def _write_csv_header(self):
        with open(f'{self.output_path}.csv', 'w') as fh:
            csv_writer = csv.DictWriter(fh, fieldnames=self.csv_field_names, delimiter=',', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writeheader()


    """
    Write results to a csv
    """
    def _write_csv(self):
        with open(f'{self.output_path}.csv', 'a') as fh:
            csv_writer = csv.DictWriter(fh, fieldnames=self.csv_field_names, delimiter=',', quoting=csv.QUOTE_MINIMAL)
            for person in self.results:
                csv_writer.writerow(person)


    """
    Write results as json objects to a file
    """
    def _write_json(self):
        with open(f'{self.output_path}.json', 'a') as fh:
            for person in self.results:
                fh.write(f'{json.dumps(person)}\n')


"""
Perform Googledork search for a company

param company: Target company for search

return str: A link to a Zoom employee profile page for `company`.
"""
def search_google(company):
    click.secho(f'[+] google-dorking zoominfo.com for {company}...', fg='green')

    search_url = 'https://www.google.com/search'
    params = {
        'q': f'site:zoominfo.com "{company}" Employee Profiles',
    }
    response = requests.get(search_url, params=params, headers=headers, proxies=proxies, verify=False)
    search_results_page = BeautifulSoup(response.content, 'html.parser')

    # Find all links in results page
    result_anchors = search_results_page.find_all('a')

    # Google's result links are wrapped in "<div class='r'></div>". Grab them all
    search_result_links = [anchor for anchor in result_anchors if anchor.parent.get('class') and 'r' in anchor.parent.get('class')]

    zoom_links = []
    pat = re.compile(r'(?P<company>.+) \| ZoomInfo.com')
    # only get top 5 search results
    for link in search_result_links[:5]:
        matched = False
        # Capture both direct employee profiles links ('/pic/') and company
        # profiles links ('/c/'). Everything else is invalid
        if '/c/' in link.get('href') or '/pic/' in link.get('href'):
            # Use the `pat` regex to capture the company value in the title of the page.
            # if there is a partial match, consider the link good, otherwise, add link to list with `matched=False`
            result_company = pat.search(link.text).group('company')
            if company in result_company:
                matched = True
            zoom_links.append({
                'result_company': result_company,
                'matched': matched,
                'link': link,
            })
    
    # Evaluate all non-matches and let the user choose which option matches their company
    if not len([link for link in zoom_links if link['matched'] == True]):
        click.secho(f'[!] failed to get an exact match on "{company}", these are the top search results:', fg='yellow')
        for i, link in enumerate(zoom_links):
            click.secho(f'    [!] {i + 1}: {link["result_company"]}', fg='yellow')
        choice = click.prompt(click.style('    [!] which search result matches your company (99 to exit)', fg='yellow'),type=int)
        if choice not in [x for x in range(1, len(zoom_links) + 1)]:
            click.secho(f'    [!] choice {choice} is not a valid choice. exiting!', fg='yellow')
            sys.exit(-1)
        link = zoom_links[choice - 1]['link']

        # If the link chosen is a company profile, swap out the URLs to point to
        # employee profiles
        if '/c/' in link.get('href'):
            link = link.get('href').replace('/c/', '/pic/')
    else:
        link = zoom_links[0]['link'].get('href')
    return link


"""
Determine if the value of a target matches a zoom URL or not

param target: str value of user input

return bool: True if target matches zoominfo regex pattern, False if not
"""
def is_valid_zoom_link(target):
    link_pattern = re.compile(r'https?:\/{2,}([\w\d]+\.)?zoominfo\.com\/(c|pic)\/([\w\d-]+\/)?\d+')
    if link_pattern.match(target):
        return True
    return False


@click.command()
@click.argument('target', type=str)
@click.option('-d', '--domain', help='The domain of the targeted company', type=str, required=True)
@click.option('-uf', '--username-format', type=click.Choice(['firstlast', 'firstmlast', 'flast', 'first.last', 'first_last', 'fmlast', 'full']), required=True)
@click.option('-o', '--output-dir', help='Save results to path', type=click.Path())
@click.option('-of', '--output-format', type=click.Choice(['flat', 'csv', 'json']))
@click.option('-q', '--quiet', is_flag=True, help='Hide banner at runtime')
def main(target, domain, username_format, output_dir, output_format, quiet):
    if not quiet:
        click.secho(banner, fg='red')

    # Determine if target argument is a zoom link or if it's a keyword and set
    # `link` to either the target URL or the result gathered from the google search
    link = target if is_valid_zoom_link(target) else search_google(target)

    # Initialize ZoomScraper object for a zoominfo.com link along with user-provided options.
    # Scrape first page and store the number of result pages to scrape.
    # Scrape subsequent pages.
    scraper = ZoomScraper(link, output_dir, output_format, username_format, domain)
    scraper.scrape(store_pagecount=True)
    scraper.scrape_pages()

if __name__ == '__main__':
    main()

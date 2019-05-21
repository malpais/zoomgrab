#!/usr/bin/env python
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
PageScraper - A wrapper class to use cfscrape

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
class PageScraper():
    url = ''
    scraper = None
    tokens = {}
    user_agent = ''

    """
    Instantiate PageScraper

    param: url - URL of target
    
    Initializes a cfscrape scraper object and performs an initial GET request
    to the target URL to acquire cloudflare-specific tokens for future use
    """
    def __init__(self, url):
        self.url = url
        self.scraper = cfscrape.create_scraper(delay=10)
        self.tokens, self.user_agent = cfscrape.get_tokens(url, proxies=proxies, verify=False)

    """
    Scrape page at URL

    param url: URL of target (optional)

    Performs a GET of an initialized URL or a new URL from the user. Cloudflare
    tokens retrieved in __init__() are re-used during scraping. Finally, parse 
    any scraped HTML with BeautifulSoup and return the bs4 object.
    """
    def scrape(self, url=''):
        if not url:
            url = self.url
        response = self.scraper.get(url, cookies=self.tokens, proxies=proxies, verify=False)
        if response.status_code != 200:
            return False
        page = BeautifulSoup(response.content, 'html.parser')
        return page


"""
Convert HTML into person data

param row_element: BeautifulSoup row object containing person data
param email_format_string: User-provided string to determine the output format of parsed username
param domain: User-provided string to append to converted username data

return dict: Dictionary value of parsed person data from HTML row.
"""
def parse_employee_info(row_element, email_format_string='', domain=''):
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
        # Split up a name into parts for parsing
        # 
        # 'Joe Z. Dirt' -> ['Joe', 'Z', 'Dirt']
        # 'Mary Skinner' -> ['Mary', 'Skinner']
        name_parts = person_name.replace('.', '').split(' ')

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
        'name': person_name,
        'title': person_title,
        'location': person_location,
        'email': f'{username.lower()}@{domain}',
    }


"""
Perform Googledork search for a company

param company: Target company for search

return str: A link to a Zoom employee profile page for `company`.
"""
def search_google(company):
    search_url = 'https://www.google.com/search'
    params = {
        'q': f'site:zoominfo.com "{company}" Employee Profiles',
    }
    response = requests.get(search_url, params=params,
                            headers=headers, proxies=proxies, verify=False)
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
Determine result counts from Zoominfo

param page_content: BeautifulSoup page object of a zoom result

return tuple: Total contacts found across a count of zoom pages
"""
def get_resultcount_pages(page_content):
    # Regex to match the counter text in the first page of results
    zoom_total_contacts_pattern = re.compile(r'of (?P<num_contacts>\d+) Contacts')
    total_search_pages = page_content.find('h2', {
        'class': 'page_numberOfResults_header',
    })
    zoom_total_contacts = zoom_total_contacts_pattern.search(total_search_pages.text).group('num_contacts')
    zoom_page_count = math.ceil(int(zoom_total_contacts) / 25)
    return (zoom_total_contacts, zoom_page_count)


@click.command()
@click.option('-c', '--company', help='The company you wish to perform OSINT on', type=str, required=True)
@click.option('-d', '--domain', help='The domain of the targeted company', type=str, required=True)
@click.option('-uf', '--username-format', type=click.Choice(['firstlast', 'firstmlast', 'flast', 'first.last', 'first_last', 'fmlast', 'full']), required=True)
@click.option('-o', '--output-dir', help='Save results to path', type=click.Path())
@click.option('-of', '--output-format', type=click.Choice(['flat', 'csv', 'json']))
def main(company, domain, username_format, output_dir, output_format):
    click.secho(banner, fg='red')

    # If the output directory doesn't exist then create it
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    click.secho(f'[+] google-dorking zoominfo.com for {company}...', fg='green')
    link = search_google(company)

    # Scrape page #1 of zoom search result
    page_scraper = PageScraper(link)
    zoom_page = page_scraper.scrape()
    if not zoom_page:
        click.secho('[!] failed to retrieve initial zoom result page... exiting.', fg='red')
        sys.exit(-1)

    total_contacts, page_count = get_resultcount_pages(zoom_page)
    click.secho(f'[+] found {total_contacts} records across {page_count} pages of results...', fg='green')
    click.secho(f'[+] starting scrape of {page_count} pages. scraping cloudflare sites can be tricky, be patient!', fg='green')

    # Loop through all subsequent pages for company and scrape the page data. This creates
    # a list of scraped page content to be parsed next.
    zoom_pages = []
    for page in [f'{link}?pageNum={x}' for x in range(2, page_count + 1)]:
        zoom_pages.append(page_scraper.scrape(page))
    zoom_pages.insert(0, zoom_page)

    click.secho('[+] scraping completed, parsing people data now...', fg='green')
    person_results = []
    for page_content in zoom_pages:
        for row in page_content.findAll('tr', {'class': 'tableRow'})[1:]:
            person_results.append(parse_employee_info(
                row, username_format, domain))

    # Depending on user-input, save the data to disk
    click.secho('[+] all done parsing people data, saving/printing results!', fg='green')
    if output_dir and output_format == 'flat':
        with open(f'{output_dir}/{domain}-{username_format}.txt', 'a') as fh:
            for person in person_results:
                fh.write(f'{person["username"]}|{person["name"]}|{person["title"]}|{person["location"]}\n')
    elif output_dir and output_format == 'csv':
        with open(f'{output_dir}/{domain}-{username_format}.csv', 'a') as fh:
            field_names = ['email', 'name', 'title', 'location']
            writer = csv.DictWriter(fh, fieldnames=field_names, delimiter=',', quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            for person in person_results:
                writer.writerow(person)
    elif output_dir and output_format == 'json':
        with open(f'{output_dir}/{domain}-{username_format}.json', 'a') as fh:
            for person in person_results:
                fh.write(f'{json.dumps(person)}\n')

    # Print results to stdout
    for person in person_results:
        click.echo(f'[*] {person["email"]}|{person["name"]}|{person["title"]}|{person["location"]}')


if __name__ == '__main__':
    main()

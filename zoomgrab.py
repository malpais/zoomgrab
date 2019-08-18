#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import re
import sys
import argparse
import requests
import click
from bs4 import BeautifulSoup
from zoom_scraper import ZoomScraper

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
    pat = re.compile(r'(?P<company>.+) | ZoomInfo.com')
    # only get top 5 search results
    for link in search_result_links[:5]:
        matched = False
        # Capture both direct employee profiles links ('/pic/') and company
        # profiles links ('/c/'). Everything else is invalid
        if '/c/' in link.get('href') or '/pic/' in link.get('href'):
            # Use the `pat` regex to capture the company value in the title of the page.
            # if there is a partial match, consider the link good, otherwise, add link to list with `matched=False`
            try:
                result_company = pat.search(link.text).group('company')
                if company in result_company:
                    matched = True
                zoom_links.append({
                    'result_company': result_company,
                    'matched': matched,
                    'link': link,
                })
            except Exception as e:
                click.secho(f'[!] failed to find a regex match for \'company\' field', fg='yellow')
    
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
@click.option('-uf', '--username-format', type=click.Choice(['firstlast', 'firstmlast', 'flast', 'first.last', 'first_last', 'fmlast', 'lastf', 'full']), required=True)
@click.option('-o', '--output-dir', help='Save results to path', type=click.Path())
@click.option('-of', '--output-format', type=click.Choice(['flat', 'csv', 'json']))
@click.option('-q', '--quiet', is_flag=True, help='Hide banner at runtime')
@click.option('-gpu', '--gophish-url', type=str, help='Admin URL for GoPhish instance')
@click.option('-gpk', '--gophish-api-key', type=str, help='API key fo GoPhish instance')
def main(target, domain, username_format, output_dir, output_format, quiet, gophish_url, gophish_api_key):
    if not quiet:
        click.secho(banner, fg='red')

    # Determine if target argument is a zoom link or if it's a keyword and set
    # `link` to either the target URL or the result gathered from the google search
    link = target if is_valid_zoom_link(target) else search_google(target)

    # Initialize ZoomScraper object for a zoominfo.com link along with user-provided options.
    # Scrape first page and store the number of result pages to scrape.
    # Scrape subsequent pages.
    scraper = ZoomScraper(link, output_dir, output_format, username_format, domain, gophish_url, gophish_api_key)
    scraper.scrape(store_pagecount=True)
    scraper.scrape_pages()

if __name__ == '__main__':
    main()

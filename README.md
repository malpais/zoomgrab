```
                    ███████╗ ██████╗  ██████╗ ███╗   ███╗ ██████╗ ██████╗  █████╗ ██████╗
                    ╚══███╔╝██╔═══██╗██╔═══██╗████╗ ████║██╔════╝ ██╔══██╗██╔══██╗██╔══██╗
                      ███╔╝ ██║   ██║██║   ██║██╔████╔██║██║  ███╗██████╔╝███████║██████╔╝
                     ███╔╝  ██║   ██║██║   ██║██║╚██╔╝██║██║   ██║██╔══██╗██╔══██║██╔══██╗
                    ███████╗╚██████╔╝╚██████╔╝██║ ╚═╝ ██║╚██████╔╝██║  ██║██║  ██║██████╔╝
                    ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝
```
zoomgrab is an OSINT tool designed to scrape employee data from zoominfo.com. Due to Cloudflare's anti-bot protection, this tool will intelligently sleep for up to 10s if Cloudflare issues an HTTP 429 Too Many Requests response. This is a Python3 project and is not meant to be run in a 2.x environment.

## Caveats
Simply put, this script does something that Cloudflare is trying to prevent. When used sparingly, this script should work fairly well. If you hammer zoominfo.com by using this script repeatedly and in rapid succession, both Cloudflare and Zoominfo.com will throw some 5xx errors back and the script will produce inconsistent results. If you see too many errors running this script, try waiting for 5 minutes, uncomment the proxy config, load burp and rerun the script to ensure everything looks alright.

## What's New
v1.5:
  * New Feature: GoPhish API integration to automatically import scraped results into a GoPhish user group ([see gophish integration summary](#gophish-integration))
  * Enhancement: Added `lastf` (last name, first initial) username format to accepted format options
  * Enhancement: Added graceful handling of regular expression match failure
  * Bug Fix: Regular expression fixes for matching company names in Google search results
  * Bug Fix: Regular expression fixes for cases where a company has only one page of results in ZoomInfo.com

## Requirements
[Node.js](https://nodejs.org/) is required by the Cloudflare anti-bot library. It serves to interpret Cloudflare's obfuscated JavaScript challenge. Without this, zoomgrab will not work as it will have no way of responding to Cloudflare's anti-bot challenge.

Python3 packages:
  * requests
  * click
  * cfscrape
  * beautifulsoup4
  * gophish


## Basic Usage
```
$ git clone https://github.com/MooseDojo/zoomgrab
$ cd zoomgrab
$ pip install -r requirements.txt
$ python zoomgrab.py --help
Usage: zoomgrab.py TARGET [OPTIONS]

Options:
  -d, --domain TEXT               The domain of the targeted company [required]
  -uf, --username-format          [firstlast|firstmlast|flast|first.last|first_last|fmlast|lastf|full] [required]
  -o, --output-dir PATH           Save results to path
  -of, --output-format            [flat|csv|json]
  -q, --quiet                     Hide banner at runtime
  -gpu, --gophish-url TEXT        Admin URL for GoPhish instance
  -gpk, --gophish-api-key TEXT    API key fo GoPhish instance
  --help                          Show this message and exit.
```

#### Sample Output:
```
$ python zoomgrab.py "Rapid7" -d Rapid7.com -uf first_last -o results -of csv -q

[+] google-dorking zoominfo.com for Rapid7...
[+] found 645 records across 26 pages of results...
[+] starting scrape of 26 pages. scraping cloudflare sites can be tricky, be patient!
[+] scraping page 1/26...
[+] scraping page 2/26...
... trimmed ...
[+] scraping page 26/26...
[*] shalini_mehan@Rapid7.com|Shalini Mehan||United States, Massachusetts, Boston
[*] troy_lamagna@Rapid7.com|Troy Lamagna|Incident Detection & Response Account Executive|United States, Massachusetts, Boston
[*] nicki_tucker@Rapid7.com|Nicki Tucker|International Manager, Demand Generation|United States, Massachusetts, Boston
...
```

#### Target Options:
zoomgrab accepts two formats for the `TARGET` argument:
  * Company name
  * zoominfo.com link to company's employee profile (will have `/pic/` in the URL)

If a company name is provided, the script will perform a Google search for ZoomInfo.com Employee Profile pages matching that company name. If the company name provided is ambiguous and Google does not find an accurate match, the top 5 search results will be shown and the user will be prompted to select a result that best matches the target company. For example:

```
$ python zoomgrab.py "MooseLife" -d moose.info -uf flast -o results -of csv -q

[+] google-dorking zoominfo.com for MooseLife...
[!] failed to get an exact match on "MooseLife", these are the top search results:
    [!] 1: Moose Inc
    [!] 2: Waymo LLC
    [!] 3: BOOST INSURANCE USA INC
    [!] 4: Bunker Protect, Inc.
    [!] 5: Slice Labs Inc.
    [!] which search result matches your company (99 to exit): 1
[+] found 43 records across 2 pages of results...
[+] starting scrape of 2 pages. scraping cloudflare sites can be tricky, be patient!
```

The second format for `TARGET` is a zoominfo.com URL to a company profile or the company's employee profile. Instead of google dorking the company, zoomgrab will take the URL provided and scrape employee data immediately. An example of this is:

```
$ python zoomgrab.py https://www.zoominfo.com/pic/rapid7-inc/32129583 -d Rapid7.com -uf first_last -o results -of csv -q

[+] found 645 records across 26 pages of results...
[+] starting scrape of 26 pages. scraping cloudflare sites can be tricky, be patient!
[+] scraping page 1/26...
[+] scraping page 2/26...
... trimmed ...
[+] scraping page 26/26...
[*] shalini_mehan@Rapid7.com|Shalini Mehan||United States, Massachusetts, Boston
[*] troy_lamagna@Rapid7.com|Troy Lamagna|Incident Detection & Response Account Executive|United States, Massachusetts, Boston
[*] nicki_tucker@Rapid7.com|Nicki Tucker|International Manager, Demand Generation|United States, Massachusetts, Boston
```

## GoPhish Integration
Gathering OSINT on a company's employees is a common task for phishing exercises, so it would make sense to have some way to import scraped employee data directly into a phishing framework. By using the gophish API, zoomgrab will automatically import data scraped from zoominfo.com into a gophish user group. 

Users are imported into gophish under the group name '[domain]-all' and any subsequent runs of zoomgrab will update existing records with any new values. An example of this may be when the user uses the wrong username format for a batch. If imported into gophish, a user group for [domain] will contain records with bad email addresses. Re-running zoomgrab with a new username format and the gophish API details will replace all changed values with the values of the second batch.

The value for option `-gpu` will be the admin URL for the gophish instance (e.g. https//<i></i>127.0.0.1:3333). The value for option `-gpk` will be the API key found in the gophish admin portal under 'Account Settings'.

```
$ python zoomgrab.py "Rapid7" -d Rapid7.com -uf first_last -o results -of csv -q -gpu https://127.0.0.1:3333 -gpk [gophish-api-key]
[+] found 645 records across 26 pages of results...
[+] starting scrape of 26 pages. scraping cloudflare sites can be tricky, be patient!
[+] scraping page 1/26...
[+] scraping page 2/26...
... trimmed ...
[+] scraping page 26/26...
[*] shalini_mehan@Rapid7.com|Shalini Mehan||United States, Massachusetts, Boston
[*] troy_lamagna@Rapid7.com|Troy Lamagna|Incident Detection & Response Account Executive|United States, Massachusetts, Boston
[*] nicki_tucker@Rapid7.com|Nicki Tucker|International Manager, Demand Generation|United States, Massachusetts, Boston
... trimmed ...
[+] gophish > adding users to group 'rapid7-all'
```

If an existing user group exists in gophish for this domain, the gophish import process will be shown as:
```
[+] gophish > updating existing users group 'rapid7-all'
```

Once zoomgrab finishes scraping employee profiles, the user group in gophish will reflect the newly imported user list for the harvested domain:

![scraped employee data imported into gophish](https://i.imgur.com/mjURJgr.png "Scraped employee data imported into gophish")


## Additional Information
If you have any feedback, please see me on Slack, otherwise please submit an issue to the tracker for bug fixes or feature requests. This is a work in progress when I'm able to spend time on it, so please be nice! If you like it, let me know!

# zoomgrab
zoomgrab is an OSINT tool designed to scrape employee data from zoominfo.com. Due to Cloudflare's anti-bot protection, this tool will intelligently sleep for up to 10s if Cloudflare issues an HTTP 429 Too Many Requests response. This is a Python3 project and is not meant to be run in a 2.x environment.

## requirements
[Node.js](https://nodejs.org/) is required by the Cloudflare anti-bot library. It serves to interpret Cloudflare's obfuscated JavaScript challenge. Without this, zoomgrab will not work as it will have no way of responding to Cloudflare's anti-bot challenge.

Python3 packages:
  * requests
  * click
  * cfscrape
  * beautifulsoup4


## usage
```
$ git clone https://github.com/MooseDojo/zoomgrab
$ cd zoomgrab
$ pip install -r requirements.txt
$ python zoomgrab.py --help
Usage: zoomgrab.py [OPTIONS]

Options:
  -c, --company TEXT              The company you wish to perform OSINT on
                                  [required]
  -d, --domain TEXT               The domain of the targeted company
                                  [required]
  -uf, --username-format [firstlast|firstmlast|flast|first.last|first_last|fmlast|full]
                                  [required]
  -o, --output-dir PATH           Save results to path
  -of, --output-format [flat|csv|json]
  --help                          Show this message and exit.
```

Sample output:
```
python parse.py -c "Rapid7" -d Rapid7.com -uf first_last -o results -of csv

███████╗ ██████╗  ██████╗ ███╗   ███╗ ██████╗ ██████╗  █████╗ ██████╗
╚══███╔╝██╔═══██╗██╔═══██╗████╗ ████║██╔════╝ ██╔══██╗██╔══██╗██╔══██╗
  ███╔╝ ██║   ██║██║   ██║██╔████╔██║██║  ███╗██████╔╝███████║██████╔╝
 ███╔╝  ██║   ██║██║   ██║██║╚██╔╝██║██║   ██║██╔══██╗██╔══██║██╔══██╗
███████╗╚██████╔╝╚██████╔╝██║ ╚═╝ ██║╚██████╔╝██║  ██║██║  ██║██████╔╝
╚══════╝ ╚═════╝  ╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝

An OSINT tool designed to scrape employee data from zoominfo.com.
Results may be delayed due to bypassing Cloudflare's anti-bot protection.

Author: Steve Coward (steve_coward@rapid7.com)

[+] google-dorking zoominfo.com for Rapid7...
    [+] fetched 1 links to employee profiles from google...
[+] found 646 records across 26 pages of results...
    [+] starting scrape of 26 pages. scraping cloudflare sites can be tricky, be patient!
    [+] scraping completed, parsing people data now...
    [+] all done parsing people data, saving/printing results!
[*] shalini_mehan@Rapid7.com|Shalini Mehan||United States, Massachusetts, Boston
[*] eric_deshaies@Rapid7.com|Eric Deshaies|Manager|United States, Massachusetts, Boston
[*] elisa_rascia@Rapid7.com|Elisa Rascia||United States, Massachusetts, Boston
[*] kristina_leblanc@Rapid7.com|Kristina LeBlanc|Marketing Specialist|United States, Massachusetts, Boston
[*] alexander_pratt@Rapid7.com|Alexander Pratt|Mid-Atlantic Incident Detection & Response Account Executive|United States, Massachusetts, Boston
[*] corey_thomas@Rapid7.com|Corey E. Thomas|Chief Executive Officer|United States, Massachusetts, Boston
[*] troy_lamagna@Rapid7.com|Troy Lamagna|Incident Detection & Response Account Executive|United States, Massachusetts, Boston
[*] alex_page@Rapid7.com|Alex Page|Detection & Response Director, Sales|United States, Massachusetts, Boston
[*] danielle_ain@Rapid7.com|Danielle Ain|Sales Manager, Coast, Detection & Response (East)|United States, Massachusetts, Boston
... trimmed ...
```

## additional information
If you have any feedback, please see me on Slack, otherwise please submit an issue to the tracker for bug fixes or feature requests. This is a work in progress when I'm able, so please be nice! If you like it, let me know!

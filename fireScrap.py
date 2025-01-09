# This script is used to extract information abouts sites web

import sys
import requests
from bs4 import BeautifulSoup
import argparse
import signal


def display_banner():
    banner = """
________                        ____                                     
`MMMMMMM 68b                   6MMMMb                                  
 MM     Y89                  6M'    `                                   
 MM      ___ ___  __   ____   MM         ____  ___  __    ___  __ ____   
 MM   ,  `MM `MM 6MM  6MMMMb  YM.       6MMMMb.`MM 6MM  6MMMMb `M6MMMMb  
 MMMMMM   MM  MM69 " 6M'  `Mb  YMMMMb  6M'   Mb MM69 " 8M'  `Mb MM'  `Mb 
 MM   `   MM  MM'    MM    MM      `Mb MM    `' MM'        ,oMM MM    MM 
 MM       MM  MM     MMMMMMMM       MM MM       MM     ,6MM9'MM MM    MM 
 MM       MM  MM     MM             MM MM       MM     MM'   MM MM    MM 
 MM       MM  MM     YM    d9 L    ,M9 YM.   d9 MM     MM.  ,MM MM.  ,M9 
_MM_     _MM__MM_     YMMMM9  MYMMMM9   YMMMM9 _MM_    `YMMM9'YbMMYMMM9  
                                                                MM       
                                                                MM       
                                                               _MM_      
                   FireScrap - Web Scraping Made Easy!
    """
    print(banner)


def bye(signal, frame):
    """Signal handler to gracefully exit the script."""
    print("\nProgram stopped by the user.")
    sys.exit(0)


def get_information_from_file(file_path):
    """Reads a file and extracts URLs line by line."""
    try:
        with open(file_path, 'r') as file:
            urls = [line.strip() for line in file.readlines()]
        return urls
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error while reading the file: {e}")
        sys.exit(1)


def get_site_content(url):
    """Fetches and parses a website's content."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as conn_err:
        print(f"Connection error occurred: {conn_err}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return None


def extract_information(site):
    """Extracts detailed information from a parsed website."""
    if not site:
        return {}
    return {
        'title': site.title.string if site.title else 'No Title',
        'links': [link.get('href') for link in site.find_all('a') if link.get('href')],
        'text': site.get_text(),
        'images': [img.get('src') for img in site.find_all('img')],
        'headers': {
            'h1': [h1.get_text() for h1 in site.find_all('h1')],
            'h2': [h2.get_text() for h2 in site.find_all('h2')],
            'h3': [h3.get_text() for h3 in site.find_all('h3')],
            'h4': [h4.get_text() for h4 in site.find_all('h4')],
            'h5': [h5.get_text() for h5 in site.find_all('h5')],
            'h6': [h6.get_text() for h6 in site.find_all('h6')]
        },
        'tables': [table.get_text() for table in site.find_all('table')]
    }


def handle_arguments(args, site):
    """Handles user-defined arguments and performs actions accordingly."""
    if not site:
        print("Error: Unable to process the website.")
        return

    extracted_data = {}

    if args.links:
        links = [link.get('href')
                 for link in site.find_all('a') if link.get('href')]
        print("\nFound Links:")
        for link in links:
            print(link)
        extracted_data['links'] = links

    if args.images:
        images = [img.get('src') for img in site.find_all('img')]
        print("\nFound Images:")
        for image in images:
            print(image)
        extracted_data['images'] = images

    if args.tables:
        tables = [table.get_text() for table in site.find_all('table')]
        print("\nFound Tables:")
        for table in tables:
            print(table)
        extracted_data['tables'] = tables

    if args.all_info:
        info = extract_information(site)
        print("\nComplete Information Extracted:")
        for key, value in info.items():
            print(f"{key.capitalize()}:\n{value}\n{'-' * 40}")
        extracted_data['Info'] = info

    if args.headers:
        headers = site.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        print("\nFound Headers:")
        for header in headers:
            print(header.get_text())
        extracted_data['headers'] = [header.get_text() for header in headers]

    if args.output:
        save_information(args.output, extracted_data)


def save_information(file_path, data):
    """Saves extracted information to a file."""
    try:
        with open(file_path, "w") as file:
            file.write(str(data))
        print(f"\nInformation saved to '{file_path}'.")
    except Exception as e:
        print(f"Error while saving the information: {e}")


def main():

    display_banner()

    parser = argparse.ArgumentParser(
        prog="scraping.py",
        usage="%(prog)s [options]",
        description="Script to extract information from websites.",
        epilog="Examples: scraping.py https://www.google.com -ai -o info.txt"
    )
    parser.add_argument(
        'url', nargs='?', help='URL of the website to analyze.')
    parser.add_argument('-a', '--archive',
                        help='File containing a list of URLs.')
    parser.add_argument('-l', '--links', action='store_true',
                        help='List all links.')
    parser.add_argument('-i', '--images', action='store_true',
                        help='List all images.')
    parser.add_argument('-t', '--tables', action='store_true',
                        help='List all tables.')
    parser.add_argument('-ai', '--all_info', action='store_true',
                        help='Display all extracted information.')
    parser.add_argument('-he', '--headers',
                        action='store_true', help='List all headers.')
    parser.add_argument(
        '-o', '--output', help='File path to save extracted information.')

    args = parser.parse_args()

    if not args.url and not args.archive:
        print("Error: You must provide a URL or a file with URLs.")
        parser.print_help()
        sys.exit(1)

    if args.archive:
        urls = get_information_from_file(args.archive)
        for url in urls:
            print(f"\nAnalyzing: {url}")
            site = get_site_content(url)
            handle_arguments(args, site)
    elif args.url:
        print(f"\nAnalyzing: {args.url}")
        site = get_site_content(args.url)
        handle_arguments(args, site)

    signal.signal(signal.SIGINT, bye)


if __name__ == '__main__':
    main()

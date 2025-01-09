
# FireScrap - Web Scraping Made Easy

FireScrap is a versatile Python-based tool designed to make web scraping easy and efficient. It allows users to extract various types of data from websites such as links, images, headers, tables, and more. Whether you're scraping a single URL or working with a list of URLs, FireScrap provides a powerful, user-friendly command-line interface for retrieving detailed information.

## Features

- **Extract links**: Retrieve all links (`<a href>`) on a webpage.
- **Extract images**: Gather the `src` attributes of all images (`<img>`) on the page.
- **Extract tables**: Parse and display all tables from a webpage.
- **Extract headers**: Fetch headers (`<h1>` to `<h6>`) from the page.
- **Complete information**: Option to retrieve all available data from the webpage, including text, images, links, headers, and tables.
- **Output to file**: Save the extracted data to a file for later use.
- **Single or bulk scraping**: Supports scraping of individual URLs or reading from a file containing a list of URLs.

## Installation

To use FireScrap, you need to have Python installed on your system. You also need to install the required dependencies.

### Step 1: Clone the repository

```bash
git clone https://github.com/yourusername/FireScrap.git
cd FireScrap
```

### Step 2: Install the dependencies

FireScrap uses `requests` and `beautifulsoup4` for web scraping. Install them using pip:

```bash
pip install -r requirements.txt
```

Alternatively, you can manually install the dependencies:

```bash
pip install requests beautifulsoup4
```

## Usage

FireScrap is run from the command line. Here are the available options:

### Command Line Arguments

- **`url`**: (Optional) The URL of the website to scrape.
- **`-a, --archive`**: (Optional) Path to a file containing a list of URLs to scrape.
- **`-l, --links`**: (Optional) List all links (`<a href>`) found on the page.
- **`-i, --images`**: (Optional) List all images (`<img src>`) found on the page.
- **`-t, --tables`**: (Optional) List all tables (`<table>`) found on the page.
- **`-ai, --all_info`**: (Optional) Display all available extracted information (links, images, headers, tables, etc.).
- **`-he, --headers`**: (Optional) List all headers (`<h1>`, `<h2>`, etc.) found on the page.
- **`-o, --output`**: (Optional) File path where the extracted information will be saved.

### Examples

1. **Scraping a single URL**:

```bash
python scraping.py https://www.example.com -l -i
```

This command will scrape the website `https://www.example.com` and list all links and images found on the page.

2. **Scraping a list of URLs from a file**:

```bash
python scraping.py -a urls.txt -t -he -o output.txt
```

This command will read the list of URLs from `urls.txt`, extract all tables and headers, and save the results in `output.txt`.

3. **Extract all information from a single URL**:

```bash
python scraping.py https://www.example.com -ai
```

This command will extract all available information (links, images, headers, tables, etc.) from `https://www.example.com`.

## Example Output

### Links:

```bash
Found Links:
https://www.example.com/page1
https://www.example.com/page2
```

### Images:

```bash
Found Images:
https://www.example.com/image1.jpg
https://www.example.com/image2.png
```

### Tables:

```bash
Found Tables:
Table 1: (text of table 1)
Table 2: (text of table 2)
```

### Headers:

```bash
Found Headers:
Heading 1
Subheading 1
Subheading 2
```

## Save Data to a File

If you want to save the extracted information to a file, you can use the `-o` option.

Example:

```bash
python scraping.py https://www.example.com -l -o links.txt
```

This command will save all the links found on the website to `links.txt`.

## Handling Errors

- **File Not Found**: If you provide a URL file that doesn't exist, the program will output an error message and stop.
- **HTTP Errors**: If the server cannot be reached or responds with an error (e.g., 404, 500), the program will show an appropriate error message.
- **Invalid URL**: If the URL is not formatted correctly, the program will display an error.

## Contribution

Feel free to fork the repository and submit pull requests. Contributions are welcome!

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


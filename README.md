# Job Crawler

A unified command-line tool for crawling job sites with configurable settings and support for multiple platforms.

## Features

- **Multi-site Support**: Easily extensible to support multiple job sites
- **YAML Configuration**: All settings configurable via YAML files
- **Deduplication**: Automatic job deduplication based on title and company
- **Colored Output**: Enhanced terminal output with colors
- **Flexible Arguments**: Command-line interface with comprehensive options
- **Robust Error Handling**: Graceful error handling and recovery

## Project Structure

```
jobs_crawler/
├── main.py                 # Main entry point
├── itviecCrawler.py         # ITviec crawler implementation
├── configs/
│   ├── global.yaml          # Global configuration for all sites
│   └── itviec_config.yaml   # ITviec-specific configuration
├── utils/
│   ├── __init__.py
│   ├── arg_parser.py        # Command-line argument parser
│   ├── colors.py            # Terminal color utilities
│   └── load_config.py       # Configuration loading utilities
└── requirements.txt         # Python dependencies
```

## Installation

1. Clone or download the project
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

### Global Configuration (`configs/global.yaml`)

Defines which job sites are available and their configurations:

```yaml
sites:
  itviec:
    name: "ITviec"
    description: "Vietnamese IT job platform"
    config_file: "configs/itviec_config.yaml"
    crawler_module: "itviecCrawler"
    crawler_function: "crawl_itviec"
    enabled: true
```

### Site-Specific Configuration (`configs/itviec_config.yaml`)

Contains all settings for a specific crawler:

```yaml
# ITviec Crawler Configuration
BASE_URL: "https://itviec.com"

# Browser Configuration
HEADLESS: false
USER_DATA_DIR: "./playwright_user_data"
CHANNEL: "chrome"
NO_VIEWPORT: true

# Timeout Configuration (in milliseconds)
PAGE_LOAD_TIMEOUT: 60000
SELECTOR_TIMEOUT: 30000
NAVIGATION_TIMEOUT: 6000
PAGE_SLEEP_DURATION: 2

# CSS Selectors
JOB_CARD_SELECTOR: ".card-jobs-list .job-card"
NEXT_PAGE_SELECTOR: "div.page.next > a[rel='next']"
```

## Usage

### Basic Commands

List all supported job sites:
```bash
python main.py --list-sites
```

Crawl ITviec with default settings:
```bash
python main.py --site itviec
```

### Advanced Options

Run in headless mode:
```bash
python main.py --site itviec --headless
```

Use custom configuration file:
```bash
python main.py --site itviec --config my_custom_config.yaml
```

Save results to specific file:
```bash
python main.py --site itviec --output my_jobs.csv
```

Show results summary:
```bash
python main.py --site itviec --show-summary
```

Enable verbose output:
```bash
python main.py --site itviec --verbose
```

### Complete Example
```bash
python main.py --site itviec --headless --show-summary --output today_jobs.csv --verbose
```

## Command-Line Arguments

| Argument | Short | Description |
|----------|-------|-------------|
| `--site` | `-s` | Job site to crawl (required) |
| `--config` | `-c` | Path to custom configuration file |
| `--output` | `-o` | Output CSV filename |
| `--list-sites` | `-l` | List all supported job sites |
| `--headless` | | Run browser in headless mode |
| `--show-summary` | | Display results summary after crawling |
| `--verbose` | `-v` | Enable verbose output |
| `--help` | `-h` | Show help message |

## Output

The crawler saves results to a CSV file with the following columns:

- **Hash**: Unique hash for deduplication
- **Title**: Job title
- **Company**: Company name
- **Location**: Job location
- **Description**: Job description (placeholder for future enhancement)
- **Skills**: Required skills (placeholder for future enhancement)
- **Link**: Direct link to the job posting

## Adding New Job Sites

To add support for a new job site:

1. Create a new crawler module (e.g., `newsite_crawler.py`)
2. Create a configuration file (e.g., `configs/newsite_config.yaml`)
3. Add the site to `configs/global.yaml`:
```yaml
sites:
  newsite:
    name: "New Site"
    description: "Description of the new site"
    config_file: "configs/newsite_config.yaml"
    crawler_module: "newsite_crawler"
    crawler_function: "crawl_newsite"
    enabled: true
```

## Error Handling

The crawler includes comprehensive error handling:

- **Configuration errors**: Clear messages when config files are missing or invalid
- **Network errors**: Graceful handling of connection issues
- **Parsing errors**: Continues crawling even if individual job cards fail
- **Interruption**: Clean shutdown on Ctrl+C

## Dependencies

- `patchright`: Browser automation
- `pandas`: Data manipulation and CSV export
- `PyYAML`: YAML configuration file parsing

## Development

### Testing

Run the test setup script to verify everything is working:
```bash
python test_setup.py
```

### Debugging

Enable verbose mode to see detailed output:
```bash
python main.py --site itviec --verbose
```

## License

This project is open source and available under the MIT License.

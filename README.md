 ```
                        _ _          __               _
     _ __ ___   ___  __| (_) __ _   / _| ___  ___  __| |
    | '_ ` _ \ / _ \/ _` | |/ _` | | |_ / _ \/ _ \/ _` |
    | | | | | |  __/ (_| | | (_| | |  _|  __/  __/ (_| |
    |_| |_| |_|\___|\__,_|_|\__,_| |_|  \___|\___|\__,_|
```

# Media feed

The media feed provides different podcast feeds to keep track of recommended talks and give others a curated list of talks.
This allows users to subscribe to these feeds in their favorite podcast player and get an easy overview of interesting talks as well as which talks they have already watched. Just copy the raw GitHub URL of the generated feed XML file into your podcast player of choice.

It is a is an evolution of the great idea of the [200ok media feed](https://github.com/200ok-ch/media_feed).

## Features

- **Python CLI** for easy feed generation and management
- **CCC Event Search** - Search and add talks from Chaos Communication Congress events
- **RSS Feed Generation** - Generate podcast-compatible RSS feeds from YAML data

## Installation

After checking out the repository, install the package using pip:

```bash
pip install media-feed
```

## Usage

The `media-feed` command provides three main functions:

### 1. Search and Add CCC Talks

Search for talks in CCC events and add them to media YAML files. As YAML are easy to read and edit, they are used as the source format for the XML RSS feeds.

```bash
# Search in latest event in the config.yaml
media-feed add "BahnMining"

# Search in specific event
media-feed add "Security Nightmares" --event 36c3

# Search by year
media-feed add "Verkehrswende" --year 2019

# Use long description from Fahrplan instead of media feed
media-feed add "Hirne Hacken" --event 36c3 --long-desc

# Specify output file
media-feed add "Copywrongs" --event 33c3 --output media/media_33c3.yml
```

### Media file format

Media YAML files contain metadata and a list of feed items:

```yaml
meta:
  title: "36C3 media feed"
  description: "A feed for different talks of the 36C3 2019"
  author: "mxmo0rhuhn"
  link: "https://github.com/mxmo0rhuhn/media_feed"
  language: "en"
  contact:
    email: "impressum@schrimpf.ch"
    name: "impressum"
  image_url: "https://static.media.ccc.de/media/congress/2019/logo.png"
  keywords:
    - it
    - programming
    - security
  categories:
    - Technology
    - Society

feed:
  - title: "BahnMining - Pünktlichkeit ist eine Zier"
    published: "Sat, 28 Dec 2019 22:10:00 +0100"
    speakers: "David Kriesel"
    subtitle: ""
    media_url: "https://cdn.media.ccc.de/congress/2019/h264-hd/36c3-10652-deu-eng-BahnMining_-_Puenktlichkeit_ist_eine_Zier_hd.mp4"
    media_type: "video/mp4"
    media_length: "476053504"
    web_url: "https://fahrplan.events.ccc.de/congress/2019/Fahrplan/events/10652.html"
    description: >-
      Talk description here...
```

### 2. Build RSS Feeds

When you have your media YAML files ready, you can generate the RSS feeds which can be used in podcast players.

```bash
# Build all feeds
media-feed build --all

# Build specific file
media-feed build media/media_36c3.yml

# Specify output directory
media-feed build --all --output-dir custom_feeds/
```

### 3. Create New Event Configuration

In order to enable talk searching for new CCC events, you need to generate a configuration for the event first. The tool tries to automatically fetch necessary URLs and patterns.

```bash
# Generate config for a new year
media-feed new-event 2024

# Specify congress number manually
media-feed new-event 2025 --congress-number 39

# Skip URL validation
media-feed new-event 2025 --no-validate
```

#### Event configuration format

Event configurations are stored in `config.yaml`. Each event requires:

- `year`: Event year
- `congress_number`: Congress number (e.g., 36 for 36C3)
- `fahrplan_url`: URL to the Fahrplan schedule XML
- `media_feed_url`: URL to the media feed XML
- `event_pattern_head`: URL pattern prefix for talk links
- `event_pattern_tail`: URL pattern suffix for talk links

Example:

```yaml
events:
  36c3:
    year: 2019
    congress_number: 36
    fahrplan_url: "https://fahrplan.events.ccc.de/congress/2019/Fahrplan/schedule.xml"
    media_feed_url: "https://media.ccc.de/podcast-hq.xml"
    event_pattern_head: "https://fahrplan.events.ccc.de/congress/2019/Fahrplan/events/"
    event_pattern_tail: ".html"
```

## Contributing

### Media Feed Entries

To contribute new talks to the media feed, edit the appropriate YAML file in the `media/` directory.
Ensure each entry includes all required fields as shown in the YAML File Format section.

### Development

Contributions are welcome! Please ensure:

- Code passes mypy type checking
- Code is formatted with ruff
- Pre-commit hooks pass
- New features include appropriate type hints

The project provides a devcontainer for easy setup. Just open the project in a compatible IDE (like VSCode) with the devcontainer extension installed, and it will set up the environment for you.

#### Manual Development Setup

If you prefer to set up the development environment manually, follow these steps:

```bash
# Clone the repository
git clone https://github.com/mxmo0rhuhn/media_feed.git
cd media_feed

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (optional but recommended)
pre-commit install
```

#### Project Structure

```
media_feed/
├── media/                    # YAML input files with talk metadata
│   ├── media_31C3.yml
│   ├── media_32C3.yml
│   ├── media_33C3.yml
│   ├── media_36C3.yml
│   └── media_todo.yml
├── feeds/                    # Generated RSS feed XML files
│   ├── feed_31C3.xml
│   ├── feed_32C3.xml
│   └── ...
├── src/media_feed/           # Python package source
│   ├── cli.py                # Main CLI logic
│   └── rss_template.xml.j2   # Jinja2 RSS template
├── config.yaml               # Event configurations
└── pyproject.toml            # Package configuration
```

#### Code Style and Quality

- Ensure your code passes mypy type checking:

```bash
mypy src/media_feed
```

- Use ruff to check and format code:

```bash
ruff check src/
ruff format src/
```

- Install pre-commit hooks to automate code quality checks:

```bash
pre-commit install
```

Pre-commit hooks automatically run on git commit:

- Trailing whitespace removal
- YAML/TOML validation
- Ruff linting and formatting
- mypy type checking
- Automatic feed generation (when YAML files change)

## License

This project is licensed under the AGPL-3.0 License. See the [LICENSE](LICENSE) file for details.

## Credits

Based on the original idea from [200ok media feed](https://github.com/200ok-ch/media_feed).

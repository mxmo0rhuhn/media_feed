 ```
                        _ _          __               _
     _ __ ___   ___  __| (_) __ _   / _| ___  ___  __| |
    | '_ ` _ \ / _ \/ _` | |/ _` | | |_ / _ \/ _ \/ _` |
    | | | | | |  __/ (_| | | (_| | |  _|  __/  __/ (_| |
    |_| |_| |_|\___|\__,_|_|\__,_| |_|  \___|\___|\__,_|
```

# Media feed

## TL;DR - Just Want to Rate Talks?

```bash
# Install
pip install media-feed

# Rate talks interactively in any event file
media-feed rate media/media_39c3.yml

# Or rate while adding a new talk
media-feed add "BahnMining" --event 36c3

# See the best-rated talks
media-feed list-by-rating
```

That's it! Your ratings help curate the feed for everyone.

---

The media feed provides different podcast feeds to keep track of recommended talks and give others a curated list of talks.
This allows users to subscribe to these feeds in their favorite podcast player and get an easy overview of interesting talks as well as which talks they have already watched. Just copy the raw GitHub URL of the generated feed XML file into your podcast player of choice.

It is an evolution of the great idea of the [200ok media feed](https://github.com/200ok-ch/media_feed).

## Features

- **Python CLI** for easy feed generation and management
- **CCC Event Search** - Search and add talks from Chaos Communication Congress events
- **RSS Feed Generation** - Generate podcast-compatible RSS feeds from YAML data
- **Collaborative Ratings** - Rate talks with 1-5 stars, add comments, and share feedback
- **Rating Analytics** - List and sort talks by rating across all events

## Installation

After checking out the repository, install the package using pip:

```bash
pip install media-feed
```

## Usage

The `media-feed` command provides five main functions:

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

After finding a talk, you'll be prompted to rate it immediately:
```
✓ Found talk:
  Title: BahnMining - Pünktlichkeit ist eine Zier
  Speakers: David Kriesel

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Would you like to rate this talk? [Y/n]: y
Username (optional, press Enter to skip): max
Rate this talk (1-5, Enter to skip): 5
Comment (optional): Einer der besten Talks!
✓ Rating saved

✓ Added entry to media/media_36c3.yml
```

### Media file format

Media YAML files contain metadata and a list of feed items. Common fields like author, contact, and language are now centralized in `config.yaml` under the `global` section.

```yaml
meta:
  title: "36C3 media feed"
  description: "A feed for different talks of the 36C3 2019"
  image_url: "https://static.media.ccc.de/media/congress/2019/logo.png"  # Optional event-specific image

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
    categories:  # Apple Podcast categories (auto-generated from CCC track or manually specified)
      - Technology
      - Science
    feedback:  # Optional collaborative feedback section
      - rating: 5
        username: max
        comment: "Einer der besten Talks des Congress!"
      - rating: 4
        comment: "Good overview"  # Anonymous feedback
      - rating: 5
        username: anna  # Rating without comment
```

#### Categories

Categories are automatically assigned based on the CCC track when adding talks via `media-feed add`. The mapping from CCC tracks to Apple Podcast categories is configured in `config.yaml`:

- **Security**, **Hardware & Making**, **CCC** → Technology
- **Science**, **Resilience & Sustainability** → Science
- **Ethics, Society & Politics** → Society & Culture, News
- **Art & Culture** → Society & Culture, Arts
- **Entertainment** → Leisure, Arts

You can override categories when adding a talk:

```bash
# Override with custom categories
media-feed add "BahnMining" --categories "Technology,Science"

# Single category
media-feed add "Security Nightmares" --categories "Technology"
```

### 2. Build RSS Feeds

When you have your media YAML files ready, you can generate the RSS feeds which can be used in podcast players.

**Important:** By default, talks with an average rating of 2 or lower are excluded from the RSS feed. This helps curate high-quality content. Use `--all-ratings` to include all talks.

```bash
# Build all feeds (excludes talks rated ≤2)
media-feed build --all

# Build specific file
media-feed build media/media_36c3.yml

# Include all talks regardless of rating
media-feed build --all --all-ratings

# Specify output directory
media-feed build --all --output-dir custom_feeds/
```

**Rating Filter Behavior:**
- Talks rated **3-5**: Always included ✓
- Talks rated **1-2**: Excluded by default (use `--all-ratings` to include)
- **Unrated talks**: Always included ✓

#### YAML Validation

The build command automatically validates your YAML files before generating RSS feeds:

- **Warnings**: Shown but don't block generation
- **Errors** Prevent RSS generation

#### Categories

The provided categories in the media YAML are intended to give you an impression of kind of content. They are only present in the YAML files as the Apple Podcast specification requires categories at the channel level only.
Categories are auto-assigned from CCC tracks when adding talks (see the global `config.yaml` for the mapping).

### 3. Rate Talks Interactively

Quickly rate talks in an event file using an interactive CLI. This is perfect for reviewing talks you've watched and sharing your feedback with others.

```bash
# Rate talks in an event file
media-feed rate media/media_36c3.yml

# The CLI will:
# 1. Ask for your username once (optional)
# 2. Show each talk with title and speakers
# 3. Ask for rating (1-5) or Enter to skip ("didn't watch")
# 4. Ask for optional comment
# 5. Save all ratings to the YAML file
```

**Interactive example:**
```
📝 Interactive Rating Mode
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Username (optional, press Enter to skip): max

Rating as: max

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎬 BahnMining - Pünktlichkeit ist eine Zier (1/15)
   Speakers: David Kriesel

Rate this talk (1-5, Enter to skip): 5
Comment (optional): Einer der besten Talks!
✓ Saved

🎬 Security Nightmares (2/15)
   Speakers: frank, Ron

Rate this talk (1-5, Enter to skip): [Enter - skipped]
⏭️  Skipped
```

Feedback is automatically added to the RSS feed description in a formatted section:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 RATINGS (Average: 4.7/5 from 3 ratings)

⭐⭐⭐⭐⭐ (5/5) - max: Einer der besten Talks!
⭐⭐⭐⭐ (4/5) Good overview
⭐⭐⭐⭐⭐ (5/5) - anna

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Original talk description...]
```

### 4. List Talks by Rating

View all rated talks sorted by their average rating. Perfect for finding the best talks across all events.

```bash
# List all rated talks
media-feed list-by-rating

# Filter by specific event
media-feed list-by-rating --event media/media_36c3.yml

# Show only highly rated talks
media-feed list-by-rating --min-rating 4.5
```

**Output example:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Rating   Title                                              Event    # Ratings
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5.0/5    BahnMining - Pünktlichkeit ist eine Zier           36C3     2
4.7/5    Let's play Infokrieg                               36C3     3
4.5/5    Vom Ich zum Wir                                    36C3     2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total: 3 rated talk(s)
```

### 5. Create New Event Configuration

In order to enable talk searching for new CCC events, you need to generate a configuration for the event first. The tool tries to automatically fetch necessary URLs and patterns.

```bash
# Generate config for a new year
media-feed new-event 2024

# Specify congress number manually
media-feed new-event 2025 --congress-number 39

# Skip URL validation
media-feed new-event 2025 --no-validate
```

#### Configuration format

The `config.yaml` file contains both global settings and event-specific configurations.

**Global settings** (applied to all feeds):
- `contact`: Feed contact information (email, name)
- `author`: Feed author
- `link`: Project link
- `language`: Feed language
- `image_url`: Default feed image URL
- `category_mapping`: CCC track to Apple Podcast category mapping

**Event configurations** (per CCC event):
- `year`: Event year
- `congress_number`: Congress number (e.g., 36 for 36C3)
- `fahrplan_url`: URL to the Fahrplan schedule XML
- `media_feed_url`: URL to the media feed XML
- `event_pattern_head`: URL pattern prefix for talk links
- `event_pattern_tail`: URL pattern suffix for talk links

Example `config.yaml`:

```yaml
global:
  contact:
    email: impressum@schrimpf.ch
    name: impressum
  image_url: https://github.com/mxmo0rhuhn/media_feed/raw/master/media_feed.png
  author: mxmo0rhuhn
  link: https://github.com/mxmo0rhuhn/media_feed
  language: en
  category_mapping:
    Technology:
      - Security
      - Hardware & Making
      - CCC
    Science:
      - Science
      - Resilience & Sustainability
    # ... more mappings

events:
  36c3:
    year: 2019
    congress_number: 36
    fahrplan_url: "https://fahrplan.events.ccc.de/congress/2019/Fahrplan/schedule.xml"
    media_feed_url: "https://media.ccc.de/c/36c3/podcast/mp4.xml"
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
│   ├── media_37c3.yml
│   ├── media_38c3.yml
│   └── media_39c3.yml
├── feeds/                    # Generated RSS feed XML files
│   ├── feed_31C3.xml
│   ├── feed_32C3.xml
│   └── ...
├── src/media_feed/           # Python package source
│   ├── cli.py                # Main CLI logic
│   ├── ccc_api.py            # CCC media API client
│   ├── config.py             # Configuration management
│   ├── rss.py                # RSS feed generation
│   ├── rss_template.xml.j2   # Jinja2 RSS template
│   └── utils/                # Utility modules
│       ├── cache_utils.py
│       ├── file_utils.py
│       ├── http_utils.py
│       ├── logger.py
│       ├── validation_utils.py
│       └── yaml_utils.py
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

#### Roadmap

Planned features and improvements:


## License

This project is licensed under the AGPL-3.0 License. See the [LICENSE](LICENSE) file for details.

## Credits

Based on the original idea from [200ok media feed](https://github.com/200ok-ch/media_feed).

# Pull and Process Emails From Missive

## Setup

Requires Python 3.8 or higher.

```
pip install git+https://github.com/papr/missive-pull
```

### Authentification

To pull data (see below), one needs to specify:
1. The team inbox id from which the emails should be pulled
2. A valid API token

Read more about these values in the
[Missive API Getting Started documentation](https://missiveapp.com/help/api-documentation/getting-started).

To avoid having to pass these values to the programm via the CLI, they can be defined
as environment variables or in a `.env` file witht the following content:

```sh
MISSIVE_API_KEY=<missive api key>
INBOX_ID=<team inbox id>
```

## Usage

This module implements:
1. A CLI to pull and save data to a cache directory
2. A Python API to load the cached conversation and message data


### Pulling Data

```sh
Usage: missive-pull [OPTIONS]

Options:
  -v, --verbose
  -i, --inbox-id TEXT             [required]
  -key, --api-key TEXT            [required]
  -until [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]
  -delta <INTEGER TEXT>...        Format: <number> <unit: 'weeks' or 'days'>
  -c, --cache-dir DIRECTORY       [default: missive.cache.d; required]
  --help                          Show this message and exit.
```

Example:
```
missive-pull -v -until 2022-06-01
missive-pull -v -delta 12 weeks
```

After pulling the data successfully, the cache directory will contain the following
msgpack files:
- `conversations.msgpack` - Contains a list of all conversations that saw activity in
  the specified time range, including their ids. More about their content can be found
  [here](https://missiveapp.com/help/api-documentation/rest-endpoints#list-conversations).
- `messages.<conversation id>.msgpack` - Contains a list of all messages that belong to
  a given conversation (id) and were delivered within the specified time range. More
  about their content can be found
  [here](https://missiveapp.com/help/api-documentation/rest-endpoints#list-conversation-messages)

### Processing Data

#### Loading Data From Cache

```py
from missive import load_converstations, load_messages

cache_dir = "missive.cache.d"

for convo in load_converstations(cache_dir):
    messages = load_messages(cache_dir, convo["id"])
    print(f"{convo['id']=} {len(messages)=} loaded")
```

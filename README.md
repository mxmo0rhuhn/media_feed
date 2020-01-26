 ```
                        _ _          __               _
     _ __ ___   ___  __| (_) __ _   / _| ___  ___  __| |
    | '_ ` _ \ / _ \/ _` | |/ _` | | |_ / _ \/ _ \/ _` |
    | | | | | |  __/ (_| | | (_| | |  _|  __/  __/ (_| |
    |_| |_| |_|\___|\__,_|_|\__,_| |_|  \___|\___|\__,_|
```

# mxmo0rhuhn media feed

The mxmo0rhuhn media feed is a fork of the great 200 200ok media feed.
It provides different podcast feeds to keep track of watched talks and give others a curated impression of talks.


## Prerequisites

The repo contains a bunch of ruby scripts (only depending on the ruby standard library, so no need to install any gems) which might shell out to external tools to facilitate generating a RSS feed based on YAML data.
Hence you need to have the following prerequisites in place:

* ruby
* curl

If you want to use the `ccc_event.py` to search for Chaos Communication Congress talks:

* python3

## TODO
- Escape yml strings in the python script (no quotes `"`, no `@`)
- YML creation with all sane defaults
- ccc.py should be able to put into the yml directly

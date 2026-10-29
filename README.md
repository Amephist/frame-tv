# frame-tv

A small local web app for putting public-domain art on a Samsung Frame TV.
Search open-access museum collections (The Met, Cleveland Museum of Art,
Rijksmuseum, SMK, V&A, Wikimedia Commons), crop and matte a work, and upload
it to the TV's Art Mode. It also lists, shows and deletes what's already on the TV.

> [!CAUTION]
> **Caveat emptor.** None of the code in this repository has been reviewed by a
> human. It was written by an AI and published as-is. Read it before you run it,
> and assume it can be wrong.

> [!WARNING]
> **Don't be stupid.** This app has no authentication and is meant for your home
> network only. Anyone who can reach it can control your TV and make the server
> download arbitrary URLs. Don't expose it to the internet, don't port-forward it,
> and don't run it on a network you don't trust.

## Requirements

- A Samsung Frame TV with Art Mode, on the same network as the machine running the app
  (tested on a 2022 model; other firmware may behave differently)
- Python 3.10+

## Setup

```sh
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt
export FRAME_TV_IP=192.168.1.50   # your TV's address
```

Optionally, run `python explore.py` first to check that the TV answers. On the first
connection the TV shows an "Allow access?" prompt; accept it with the remote. The
pairing token is saved to `token.txt` and reused afterwards.

## Run

```sh
uvicorn app.main:app --host 0.0.0.0 --port 8700
```

Then open `http://<this-machine>:8700` from a browser on your network. Use
`--host 127.0.0.1` if you only need it on this machine.

## Configuration

| Variable          | Default        | Purpose                                    |
| ----------------- | -------------- | ------------------------------------------ |
| `FRAME_TV_IP`     | *(required)*   | IP address of the TV                       |
| `FRAME_TV_TOKEN`  | `./token.txt`  | Where the TV pairing token is stored       |
| `FRAME_TV_DATA`   | `./data`       | Local database and thumbnail cache         |

`token.txt` and `data/` are git-ignored. Don't commit them.

## Artwork rights

The museum sources return open-access and public-domain works, but licensing
metadata isn't always right. Check the rights of any image before you do anything
with it beyond hanging it on your own wall.

## License

[MIT](LICENSE)

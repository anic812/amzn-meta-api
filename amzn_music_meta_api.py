import os
import json
import re
import random
import requests
import asyncio
from typing import List, Dict, Optional
import re
from urllib.parse import urlparse
from contr import COUNTRIES
import datetime
import time


class MusicSession:
    def __init__(self):
        self.cookies_path = "cookies.txt"
        self.LOOKUP_API_URL = (
            "https://music.amazon.com/{continent}/api/muse/legacy/lookup"
        )
        self.SEARCH_API_URL = (
            "https://music.amazon.com/{continent}/api/textsearch/search/v1_1/"
        )
        self.LYRICS_API_URL = "https://music.amazon.com/{continent}/api/xray/"
        self.metadataLanguage = "en_US"
        self.session = None
        self.appConfig = None
        self.WAIT_TIME = 1  # Define a wait time in seconds

    async def _set_session(self):
        try:
            raw_cookies = self._get_raw_cookies()
            domain = self._get_domain(raw_cookies)
            if not domain:
                raise ValueError("Invalid cookies")

            cookies = self._get_cookies(raw_cookies)
            self.session = {
                "headers": {
                    "Cookie": self._cookies_to_header(cookies),
                },
            }

            home_page_url = f"https://music{domain}"
            session = requests.Session()
            session.headers.update(self.session["headers"])
            home_page = session.get(home_page_url)
            home_page_text = home_page.text

            app_config_match = re.search(
                r"appConfig\s*:\s*({.*})\s*,", home_page_text, re.DOTALL
            )
            if not app_config_match:
                broader_match = re.search(r"({.*?})\s*,", home_page_text, re.DOTALL)
                if broader_match:
                    print(
                        "Found a broader match, but unable to confirm it's appConfig."
                    )
                else:
                    raise ValueError(
                        "Unable to find any JSON-like structure in the HTML."
                    )
            else:
                app_config_str = app_config_match.group(1)
                try:
                    self.appConfig = json.loads(app_config_str)
                except json.JSONDecodeError as json_parse_error:
                    print("Error parsing appConfig JSON:", json_parse_error.msg)
                    raise json_parse_error

                if not self.appConfig.get("customerId"):
                    pass

                self.session["headers"].update(
                    {
                        "user-agent": self._get_maestro_user_agent(True),
                        "csrf-token": self.appConfig["csrf"]["token"],
                        "csrf-rnd": self.appConfig["csrf"]["rnd"],
                        "csrf-ts": self.appConfig["csrf"]["ts"],
                    }
                )
        except Exception as error:
            print("Error setting session:", error)
            raise error

    def _get_raw_cookies(self):
        cookie_file = os.path.abspath(self.cookies_path)
        if not os.path.exists(cookie_file):
            raise FileNotFoundError(f"Cookie file not found: {cookie_file}")

        with open(cookie_file, "r", encoding="utf-8") as file:
            cookies = file.read().split("\n")

        return [
            {"name": parts[5], "value": parts[6], "domain": parts[0]}
            for line in cookies
            if line and not line.startswith("#")
            for parts in [line.split("\t")]
        ]

    def _get_domain(self, raw_cookies):
        domain_cookie = next(
            (cookie for cookie in raw_cookies if ".amazon" in cookie["domain"]), None
        )
        return domain_cookie["domain"] if domain_cookie else None

    def _get_cookies(self, raw_cookies):
        return {
            cookie["name"]: cookie["value"]
            for cookie in raw_cookies
            if ".amazon" in cookie["domain"]
        }

    def _cookies_to_header(self, cookies):
        return "; ".join(f"{key}={value}" for key, value in cookies.items())

    def _get_maestro_user_agent(self, add_uuid=False):
        random_hex_value = lambda length: "".join(
            random.choice("0123456789abcdef") for _ in range(length)
        )
        uuid = f"{random_hex_value(2)}-{random_hex_value(2)}-dmcp-{random_hex_value(2)}-{random_hex_value(2)}{random_hex_value(4)[4:5]}"
        agent = f"Maestro/1.0 WebCP/{self.appConfig['version']}"
        if add_uuid:
            agent += f" ({uuid})"
        return agent

    def sec_to_min(self, seconds: int) -> str:
        minutes = seconds // 60
        seconds %= 60
        return "{:02}:{:02}".format(minutes, seconds)

    def convert_timestamp(self, timestamp: int) -> str:
        return datetime.datetime.fromtimestamp(
            timestamp // 1000, datetime.timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S %Z")

    async def get_url_info(self, url):
        url_parts = re.match(
            r"^https?:\/\/music\.amazon\.[a-z\.]+\/(artists|albums|tracks|playlists)\/(.*?)\/?(?:\?.*)?$",
            url,
        )

        if not url_parts:
            raise "URL not supported. Please enter a valid Amazon Music URL."

        asin = re.search(r"\b([A-Z0-9]{10})\b", url)
        if not asin:
            raise "Invalid URL"

        url_type = url_parts.group(1)
        if url_type not in ["artists", "albums", "tracks", "playlists"]:
            raise "URL unrecognized. Please enter a URL for an artist, album, track, or playlist."

        country_match = re.search(r"musicTerritory=([A-Z]{2})", url)
        if not country_match:
            country = "US"
            suffix = re.match(r"^https?:\/\/music\.amazon\.(.*?)\/", url).group(1)
            for key, value in COUNTRIES.items():
                if value.get("suffix") == suffix:
                    country = key
                    break
        else:
            country = country_match.group(1)

        return {"type": url_type, "asin": asin.group(0), "country": country}

    async def get_metadata(
        self,
        asin: str,
        country: Optional[str] = None,
        features: List[str] = [
            "fullAlbumDetails",
            "playlistLibraryAvailability",
            "disableSubstitution",
            "childParentOwnership",
            "trackLibraryAvailability",
            "hasLyrics",
            "ownership",
            "expandTracklist",
            "includeVideo",
            "requestAudioVideo",
            "popularity",
            "albumArtist",
            "collectionLibraryAvailability",
            "includePurchaseDetails",
            "editorialAssociations",
        ],
    ) -> Dict:
        if not self.session:
            await self._set_session()

        country = country or self.appConfig["musicTerritory"]
        continent = COUNTRIES[country]["continent"]

        request_body = {
            "asins": [asin] if not isinstance(asin, list) else asin,
            "requestedContent": "KATANA",
            "features": features,
            "deviceType": self.appConfig["deviceType"],
            "musicTerritory": country,
            "metadataLang": self.metadataLanguage,
        }

        response = requests.post(
            self.LOOKUP_API_URL.replace("{continent}", continent),
            headers={
                **self.session["headers"],
                "X-Amz-Target": "com.amazon.musicensembleservice.MusicEnsembleService.lookup",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/json",
            },
            json=request_body,
        )

        metadata = response.json()

        if not any(
            key in metadata
            for key in ["albumList", "trackList", "playlistList", "artistList"]
        ):
            raise ValueError("Invalid metadata response")

        return await self.metadata_extract(metadata)

    async def metadata_extract(self, data: Dict) -> Dict:
        try:
            t = data["albumList"][0]
        except Exception as e:
            return {str(e): data}

        output_data = {
            "artist_name": t["artist"]["name"],
            "asin": t["globalAsin"],
            "title": t["title"],
            "duration": self.sec_to_min(t["duration"]),
            "copyright": t["productDetails"]["copyright"],
            "label": t["productDetails"]["label"],
            "price": (
                t["purchase"]["price"] + " " + t["purchase"]["currency"]
                if t["purchase"]["price"] and t["purchase"]["currency"]
                else None
            ),
            "artwork": t["image"],
            "artwork_hires": (
                await self.get_search_hires_artwork(t["globalAsin"])
                if await self.get_search_hires_artwork(t["globalAsin"])
                else "N/A"
            ),
            "original_release_date": self.convert_timestamp(t["originalReleaseDate"]),
            "content_encoding": ["sdAvailable"] + t["contentEncoding"],
            "tracks": [],
        }

        for track in t["tracks"]:
            track_dict = {
                "track_num": track["trackNum"],
                "asin": track["asin"],
                "artist": track["artist"]["name"],
                "title": track["title"],
                "isrc": track["isrc"],
                "lyrics": await self.get_lyrics(asin=track["asin"]),
                "duration": self.sec_to_min(track["duration"]),
                "songWriters": (
                    track["songWriters"] if track["songWriters"] != "null" else "N/A"
                ),
                "disc": track["discNum"],
            }
            output_data["tracks"].append(track_dict)

        return output_data

    async def get_search_hires_artwork(
        self,
        query: str,
        country: Optional[str] = None,
        search_types: List[str] = ["catalog_album"],
        limit: int = 10,
    ) -> Dict:
        if not self.session:
            await self._set_session()

        country = country or self.appConfig["musicTerritory"]
        continent = COUNTRIES[country]["continent"]
        result_specs = [
            {
                "contentRestrictions": {
                    "allowedParentalControls": {"hasExplicitLanguage": True},
                    "assetQuality": {"quality": []},
                    "contentTier": "UNLIMITED",
                    "eligibility": None,
                },
                "documentSpecs": [
                    {
                        "fields": [
                            "__default",
                            "parentalControls.hasExplicitLanguage",
                            "contentTier",
                            "artOriginal",
                            "contentEncoding",
                            "lyrics",
                        ],
                        "filters": None,
                        "type": search_type,
                    },
                ],
                "label": search_type,
                "maxResults": limit,
                "pageToken": None,
                "topHitSpec": None,
            }
            for search_type in search_types
        ]

        response = requests.post(
            self.SEARCH_API_URL.replace("{continent}", continent),
            json={
                "customerIdentity": {
                    "customerId": self.appConfig["customerId"],
                    "deviceId": self.appConfig["deviceId"],
                    "deviceType": self.appConfig["deviceType"],
                    "musicRequestIdentityContextToken": None,
                    "sessionId": "123-1234567-5555555",
                },
                "explain": None,
                "features": {
                    "spellCorrection": {
                        "accepted": None,
                        "allowCorrection": True,
                        "rejected": None,
                    },
                    "spiritual": None,
                    "upsell": {
                        "allowUpsellForCatalogContent": False,
                    },
                },
                "musicTerritory": country,
                "query": query,
                "locale": self.metadataLanguage,
                "queryMetadata": None,
                "resultSpecs": result_specs,
            },
            headers={
                **self.session["headers"],
                "X-Amz-Target": "com.amazon.tenzing.textsearch.v1_1.TenzingTextSearchServiceExternalV1_1.search",
                "Content-Encoding": "amz-1.0",
                "Content-Type": "application/json",
            },
        )

        if response.status_code != 200:
            print("estatus: " + str(response.status_code))
            raise Exception(f"HTTP error! status: {response.status_code}")

        search_results = response.json()
        if "results" not in search_results:
            raise Exception("No search results found")

        return (
            search_results["results"][0]["hits"][0]["document"]["artOriginal"]["URL"]
            if search_results["results"][0]["hits"][0]["document"]["artOriginal"]["URL"]
            else ""
        )

    async def get_lyrics(self, asin: str, country: Optional[str] = None) -> List[Dict]:
        if not self.session:
            await self._set_session()
        country = country or self.appConfig["musicTerritory"]
        continent = COUNTRIES[country]["continent"]
        response = requests.post(
            self.LYRICS_API_URL.replace("{continent}", continent),
            headers={
                **self.session["headers"],
                "X-Amz-Target": "com.amazon.musicxray.MusicXrayService.getLyricsByTrackAsinBatch",
                "Content-Encoding": "amz-1.0",
                "Content-Type": "application/json",
            },
            json={
                "trackAsinsAndMarketplaceList": [
                    {
                        "asin": asin,
                        "musicTerritory": country,
                    }
                ]
            },
        )

        lyrics = response.json()
        # pprint(lyrics)
        if not lyrics.get("lyricsResponseList") or any(
            lr.get("lyrics") is None and lr.get("lyricsResponseCode") == 2001
            for lr in lyrics["lyricsResponseList"]
        ):
            return "N/A"

        return self.convert_lyrics_to_lrc(lyrics["lyricsResponseList"][0]["lyrics"])

    def milliseconds_to_lrc_time(self, ms):
        """Convert milliseconds to LRC time format [mm:ss.xx]."""
        total_seconds = ms / 1000
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        hundredths = int((total_seconds - int(total_seconds)) * 100)
        return f"[{minutes:02}:{seconds:02}.{hundredths:02}]"

    def format_lyric_line(self, start_time, text) -> str:
        lrc_time = self.milliseconds_to_lrc_time(start_time)
        return f"{lrc_time}{text}"

    def convert_lyrics_to_lrc(self, lyrics_data):
        lrc_lines = [
            self.format_lyric_line(line["startTime"], line["text"])
            for line in lyrics_data["lines"]
        ]
        lrc_str = "\n".join(lrc_lines)
        return lrc_str


"""
# Example usage
async def main():
    start_time = time.time()
    cookies_path = "cookies.txt"
    music_session = MusicSession(cookies_path)
    url = "https://music.amazon.com/albums/B07VPSBX8J?marketplaceId=ATVPDKIKX0DER&musicTerritory=US&ref=dm_sh_PX6OVmaqjXPFEmrQ11juXzWc3"
    info = await music_session.get_url_info(url)
    print(info)
    metadata = await music_session.get_metadata(asin=info['asin'], country=info['country'])
    #print(metadata)
    with open("data.json", "w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=4)
    end_time = time.time()
    elapsed_time = end_time - start_time

    print(f"Elapsed time: {elapsed_time} seconds")


if __name__ == "__main__":
    asyncio.run(main())
"""

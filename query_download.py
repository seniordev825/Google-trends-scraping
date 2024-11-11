"""Google Trends Search Query Downloader"""
from json import dump
from csv import reader as csv_reader
from time import sleep
from random import uniform
from traceback import print_exc
from os import mkdir, getcwd, rename
from os import path as ospath
from datetime import datetime
from dataclasses import dataclass
from selenium.webdriver.common.keys import Keys
from selgym import (
    FirefoxOptions,
    FirefoxWebDriver,
    get_firefox_webdriver,
    get_firefox_options,
    wait_element_by,
    wait_elements_by,
    get_default_firefox_profile,
    scroll_into_element,
    By,
    ActionChains,
    WebElement,
)

# Absoulute path to the Root Firefox profile
FIREFOX_PROFILE = (
    r""
)

# Set browser headless behaviour, set to False for debugging
HEADLESS = False

# Range of seconds to wait for each keystroke
MIN_TYPING_SECONDS = 0.2
MAX_TYPING_SECONDS = 0.5

# Number of retries in case page doesn't load
RETRY_COUNT = 3

DEFAULT_OUTPUT_DIR = ospath.join(getcwd(), "output")

BASE_URL = "https://trends.google.com/trends/explore?date=today%203-m"

INPUT_FIELD_CSSS = 'input[id="input-29"]'
DOWNLOAD_BUTTON_CSSS = 'button[class="widget-actions-item export"]'


@dataclass
class KeywordValueEntry:
    """Dataclass for related queries"""

    keyword: str
    value: str


class GoogleTrendsDownloader:
    """Google Trends Downloader class"""

    def __init__(
        self,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        firefox_profile: str = FIREFOX_PROFILE,
        headless: bool = HEADLESS,
    ) -> None:
        self.output_dir = output_dir
        # Ensures output directory
        if not ospath.isdir(self.output_dir):
            mkdir(self.output_dir)

        self.driver: FirefoxWebDriver = None
        # Generate Firefox options for selenium
        if not firefox_profile:
            firefox_profile = get_default_firefox_profile()

        self.options: FirefoxOptions = get_firefox_options(
            firefox_profile=firefox_profile, headless=headless
        )

    def __gen_filepath(self, query: str, output_dir: str, ext: str) -> str:
        query_name = "".join(c for c in query if c.isalnum() or c in ["-", "_"])

        # Generate a timestamp for the output filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        return ospath.join(output_dir, f"{query_name}_{timestamp}.{ext}")

    def __gen_query_folder(self, query: str) -> str:
        query_name = "".join(c for c in query if c.isalnum() or c in ["-", "_"])

        query_folder_path = ospath.join(self.output_dir, query_name)
        if not ospath.isdir(query_folder_path):
            mkdir(query_folder_path)
        return query_folder_path

    def __send_text(self, text: str, input_field: WebElement) -> None:
        text = text.strip().replace("\\", "")
        for ch in text:
            sleep(uniform(MIN_TYPING_SECONDS, MAX_TYPING_SECONDS))
            input_field.send_keys(ch)

    def __query_downloader_task(
        self, query: str, retry_count: int = RETRY_COUNT
    ) -> str:

        if retry_count <= 0:
            print("\nToo many retries, quitting...")
            return

        self.driver.get(BASE_URL)

        # Wait for the input field to be visible
        # In case of errors, it indicates the page is not loading properly
        try:
            input_field = wait_element_by(
                self.driver, By.CSS_SELECTOR, INPUT_FIELD_CSSS, timeout=5
            )
        except Exception:
            # Page failed to load, retry again
            print("\nPage failed to load, retrying...")
            return self.__query_downloader_task(query, retry_count=retry_count - 1)

        # Sleep a random time before interacting with the page
        sleep(uniform(1, 2))

        # Send query keystrokes
        self.__send_text(query, input_field)

        # Perform search
        ActionChains(self.driver).key_down(Keys.CONTROL).key_down(Keys.ENTER).key_up(
            Keys.ENTER
        ).key_up(Keys.CONTROL).perform()

        # Wait for the new page to load
        sleep(5)

        # Wait for the download button in the new page.
        # If this throws errors, there was a problem performing search
        button = wait_elements_by(
            self.driver, By.CSS_SELECTOR, DOWNLOAD_BUTTON_CSSS, timeout=30
        )[-2]

        # Perform download
        scroll_into_element(self.driver, button)
        button.click()

        output_filepath = self.__gen_filepath(query, self.output_dir, "csv")

        related_entities_file = ospath.join(self.output_dir, "relatedEntities.csv")
        while not ospath.exists(related_entities_file):
            sleep(0.5)

        rename(related_entities_file, output_filepath)
        print(f"\nSuccessfully downloaded: {output_filepath}")
        return output_filepath

    def __timeline_downloader_task(
        self, query: str, output_dir: str, retry_count: int = RETRY_COUNT
    ) -> str:
        if retry_count <= 0:
            print("\nToo many retries, quitting...")
            return

        self.driver.get(BASE_URL)

        # Wait for the input field to be visible
        # In case of errors, it indicates the page is not loading properly
        try:
            input_field = wait_element_by(
                self.driver, By.CSS_SELECTOR, INPUT_FIELD_CSSS, timeout=5
            )
        except Exception:
            # Page failed to load, retry again
            print("\nPage failed to load, retrying...")
            return self.__timeline_downloader_task(query, output_dir, retry_count=retry_count - 1)

        # Sleep a random time before interacting with the page
        sleep(uniform(1, 2))

        # Send query keystrokes
        self.__send_text(query, input_field)

        # Perform search
        ActionChains(self.driver).key_down(Keys.CONTROL).key_down(Keys.ENTER).key_up(
            Keys.ENTER
        ).key_up(Keys.CONTROL).perform()

        # Wait for the new page to load
        sleep(5)

        # Wait for the download button in the new page.
        # If this throws errors, there was a problem performing search
        button = wait_element_by(
            self.driver, By.CSS_SELECTOR, DOWNLOAD_BUTTON_CSSS, timeout=30
        )

        # Perform download
        button.click()

        # Ensure the output dir is the subdirectory for the query
        output_filepath = self.__gen_filepath(query, output_dir, "csv")

        timeline_file = ospath.join(self.output_dir, "multiTimeline.csv")
        while not ospath.exists(timeline_file):
            sleep(0.1)

        rename(timeline_file, output_filepath)
        print(f"\nSuccessfully downloaded: {output_filepath}")
        return output_filepath

    def __save_json(self, data: list[KeywordValueEntry], output_path: str) -> None:
        json_data = [entry.__dict__ for entry in data]

        with open(output_path, "w", encoding="utf-8", errors="ignore") as f:
            dump(json_data, f, indent=4)

    def __parse_csv(self, csv_path: str) -> list[KeywordValueEntry] | None:
        rising_keywords = []

        with open(csv_path, "r", encoding="utf-8", errors="ignore") as csv_file:
            reader = csv_reader(csv_file)
            found_rising = False

            for row in reader:
                if found_rising:
                    if row:
                        keyword = row[0]
                        value = row[1]
                        rising_keywords.append(KeywordValueEntry(keyword, value))
                    else:
                        break
                elif row and row[0] == "RISING":
                    found_rising = True

        return rising_keywords

    def run(self, query: str) -> None:
        """Runs the bot on a search `query` list,
        saving all the downloaded files into `output_dir`"""

        # Disable "Save As" dialog, and set download folder
        self.options.set_preference("browser.download.folderList", 2)
        self.options.set_preference("browser.download.dir", self.output_dir)
        self.options.set_preference(
            "browser.helperApps.neverAsk.saveToDisk", "text/csv"
        )

        self.driver = get_firefox_webdriver(options=self.options)
        self.driver.maximize_window()
        try:
            try:
                # Gather the relevant queries
                input_filepath = self.__query_downloader_task(query)
                data = self.__parse_csv(input_filepath)
                if not data:
                    print("\nError retrieving data...")
                    return
                print(data)
                query_output_dir = self.__gen_query_folder(query)

                # Saves query data into json
                json_path = self.__gen_filepath(query, self.output_dir, "json")
                self.__save_json(data, json_path)

                # Gather all multi line data
                for entry in data:
                    self.__timeline_downloader_task(entry.keyword, query_output_dir)
                print("\nFinished!")
            except KeyboardInterrupt:
                return
            except Exception:
                print_exc()
                # Optionally handle errors,
                # for now just return in case of errors
                return
        finally:
            self.driver.quit()


def _main() -> None:

    query = input("\nInsert search query\n>>").strip()
    if not query:
        print("\nNo query inserted...")
        return

    query = query.replace(",", " ")

    print("\nDownloading query file from Google Trends, please wait...")

    # Runs the bot
    GoogleTrendsDownloader().run(query)


if __name__ == "__main__":
    _main()

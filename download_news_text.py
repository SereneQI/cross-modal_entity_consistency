import argparse
import json
import logging
import multiprocessing
from newspaper import Article
import os
import sys

# own imports
import utils


def parse_args():
    parser = argparse.ArgumentParser(description="Downloader for news texts")
    parser.add_argument("-vv", "--debug", action="store_true", help="debug output")

    parser.add_argument("-i", "--input", type=str, required=True, help="path to dataset.jsonl")
    parser.add_argument("-o", "--output", type=str, required=True, help="path to output directory")

    parser.add_argument("-d",
                        "--dataset",
                        type=str,
                        required=True,
                        choices=["News400", "TamperedNews"],
                        help="select dataset to process")

    parser.add_argument("-t", "--threads", default=32, required=False, help="number of downloader threads")

    args = parser.parse_args()
    return args


def download_news_text(args):
    outfile, url, language = args

    if os.path.isfile(outfile):
        logging.info(f"Text from already processed: {url}")
        return

    logging.info(f"Downloading text from: {url}")

    try:
        if "www.sueddeutsche.de" in url:  # BUGFIX parser for german does not work for this domain
            article = Article(url, language="en")
        else:
            article = Article(url, language=language)

        article.download()
        article.parse()

        # write text
        with open(outfile, 'w') as f:
            if language == "de":  # NOTE: News400 texts were postprocessed in our project
                news_text = article.text.replace("\t", " ")
                with open(os.path.splitext(outfile)[0] + "_text.txt", 'w') as txtfile:
                    for line in news_text.split("\n"):
                        txtfile.writelines(line)

            data = {
                'title': article.title,
                'authors': article.authors,
                'text': article.text,
                'description': article.meta_description,
                'keywords': article.meta_keywords,
                'summary': article.summary
            }

            json.dump(data, f)

        return

    except Exception as e:
        logging.warning(f'Could not download news text from: {url}')
        logging.warning(e)

        # deleting output file if created but not processed successfully
        if os.path.isfile(outfile):
            os.remove(outfile)

        return


def main():
    # load arguments
    args = parse_args()

    # define logging level and format
    level = logging.INFO
    if args.debug:
        level = logging.DEBUG

    logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=level)

    # setup output directory
    if not os.path.exists(args.output):
        os.makedirs(args.output)

    # dataset dependent parameters
    if args.dataset == "News400":
        language = "de"
    else:  # TamperedNews
        language = "en"

    # read urls from dataset.jsonl
    dataset = utils.read_jsonl(args.input, dict_key="id")
    news_urls = []
    for doc in dataset.values():
        news_urls.append([os.path.join(args.output, doc["id"] + ".json"), doc["url"], language])

    # download texts
    with multiprocessing.Pool(args.threads) as p:
        p.map(download_news_text, news_urls)

    # store texts in dataset_full.jsonl
    with open(os.path.splitext(args.input)[0] + "_with_text.jsonl", "w") as f:
        for doc in dataset.values():
            txt_file = os.path.join(args.output, doc["id"] + ".json")

            if not os.path.exists(txt_file):
                continue

            # meta information
            doc_with_text = {"id": doc["id"], "url": doc["url"], "image_url": doc["image_url"]}

            # title, text, caption
            with open(txt_file, "r") as jsonfile:
                data = json.load(jsonfile)
                doc_with_text["title"] = data["title"]

                if args.dataset == "News400":
                    # NOTE: News400 texts were postprocessed in our project
                    with open(os.path.splitext(txt_file)[0] + '_text.txt', 'r') as txt_file:
                        news_text = txt_file.read()
                    doc_with_text["text"] = utils.postprocess_text(news_text)

                else:  # TamperedNews
                    doc_with_text["text"] = data["text"]

            # NERD outputs
            doc_with_text["text_persons"] = doc["text_persons"]
            doc_with_text["text_locations"] = doc["text_locations"]
            doc_with_text["text_events"] = doc["text_events"]

            # Untampered and tampered entity sets
            doc_with_text["test_context"] = doc["test_context"]
            doc_with_text["test_persons"] = doc["test_persons"]
            doc_with_text["test_locations"] = doc["test_locations"]
            doc_with_text["test_events"] = doc["test_events"]

            f.write(json.dumps(doc_with_text) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
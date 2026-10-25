#!/usr/bin/env python

# Copyright (c) 2026 Joel Torres
# Licensed under the MIT License. See the file LICENSE for details.

import yaml
import markdown
import jinja2
import shutil
import re
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import xml.etree.ElementTree as ET

class Site:

    generator = "https://github.com/joetorx/ssg2"
    output = Path("public").absolute()
    content = Path("content").absolute()
    config = Path("site.yaml").absolute()
    date_format = "%Y-%m-%d %H:%M:%S %z"
    date_rfc822 = "%a, %d %b %Y %H:%M:%S %z"
    encoding = "UTF-8"

    def __init__(self):
        self.site = self.load_config()
        self.site["pages"] = {}

        self.theme_static = Path("static")
        self.theme_layouts = Path("layouts")

        self.md = markdown.Markdown(extensions=["meta"])
        self.layout_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.theme_layouts)
        )

    def build(self):
        print("Building site...")
        shutil.rmtree(self.output, ignore_errors=True)
        self.output.mkdir()

        # static assets
        shutil.copytree(self.theme_static, self.output / self.theme_static.name)

        # content dir traversal and markdown file parsing
        self.build_content()

        # layout rendering
        self.build_pages()

        # RSS feed build
        if self.site.get("feed"):
            self.build_feed()

    def build_content(self):
        for root, dirs, files in self.content.walk():
            content_href = str(root).replace(str(self.content), "")
            content_path = content_href[1:]
            for name in dirs:
                output_dir = self.output / content_path / name
                if ".git" in str(output_dir):
                    continue
                output_dir.mkdir()
            for name in files:
                source_file_path = root / name
                if ".git" in str(source_file_path):
                    continue

                is_md = re.search(".+(\\.md|\\.markdown)$", name)
                if is_md:
                    md_ext = is_md.group(1)
                    output_file_name = name.replace(md_ext, ".html")
                else:
                    output_file_name = name
                output_file_path = self.output / content_path / output_file_name

                if is_md:
                    page = self.parse_md_file(source_file_path)
                    page["output_path"] = output_file_path
                    page["href"] = f"{content_href}/{output_file_name}"
                    layout = page["layout"]
                    if layout not in self.site["pages"]:
                        self.site["pages"][layout] = [page]
                    else:
                        self.site["pages"][layout].append(page)
                else:
                    # copy files as is
                    source_file_path.copy(output_file_path)

    def build_pages(self):
        for layout in self.site["pages"]:
            for page in self.site["pages"][layout]:
                template = self.layout_env.get_template(f"{page['layout']}.html")
                output = template.render(site=self.site, page=page)
                self.write_file(page["output_path"], output)

    def build_feed(self):
        feed_file = "feed.xml"
        post_layout = self.site["feed"]
        if self.site["pages"].get(post_layout):
            posts = sorted(self.site["pages"][self.site["feed"]],
                           key=lambda x: x["date"], reverse=True)
        else:
            posts = []

        root = ET.Element("rss", {"version": "2.0",
                                  "xmlns:atom": "http://www.w3.org/2005/Atom"})
        channel = ET.SubElement(root, "channel")

        # required channel elements
        title = ET.SubElement(channel, "title")
        title.text = self.site["title"]
        link = ET.SubElement(channel, "link")
        link.text = self.site["url"]
        description = ET.SubElement(channel, "description")
        description.text = self.site["description"]

        # optional channel elements
        if self.site.get("lang"):
            language = ET.SubElement(channel, "language")
            language.text = self.site["lang"]
        if self.site.get("author") and self.site.get("email"):
            text = f"{self.site['email']} ({self.site['author']})"
            managingEditor = ET.SubElement(channel, "managingEditor")
            webMaster = ET.SubElement(channel, "webMaster")
            managingEditor.text = text
            webMaster.text = text
        if len(posts) > 0:
            last_post = posts[0]
            last_post_date = last_post["date"].strftime(self.date_rfc822)

            pubDate = ET.SubElement(channel, "pubDate")
            lastBuildDate = ET.SubElement(channel, "lastBuildDate")
            pubDate.text = last_post_date
            lastBuildDate.text = last_post_date
        generator = ET.SubElement(channel, "generator")
        generator.text = self.generator
        docs = ET.SubElement(channel, "docs")
        docs.text = "https://www.rssboard.org/rss-specification"

        atom_link = ET.SubElement(channel, "atom:link")
        atom_link.attrib = {
            "href": f"{self.site['url']}/{feed_file}",
            "rel": "self",
            "type": "application/rss+xml"
        }

        for post in posts:
            item = ET.SubElement(channel, "item")
            title = ET.SubElement(item, "title")
            link = ET.SubElement(item, "link")
            description = ET.SubElement(item, "description")
            guid = ET.SubElement(item, "guid")
            pubDate = ET.SubElement(item, "pubDate")

            post_link = f"{self.site['url']}{post['href']}"
            title.text = post["title"]
            link.text = post_link
            description.text = post["html"]
            guid.text = post_link
            pubDate.text = post["date"].strftime(self.date_rfc822)

        ET.indent(root)
        tree = ET.ElementTree(root)
        tree.write(self.output / feed_file, encoding=self.encoding, xml_declaration=True)

    def parse_md_file(self, file_path):
        text = self.read_file(file_path)
        html = self.md.convert(text)
        meta = self.md.Meta
        if not meta.get("layout"):
            raise Exception(f"error: layout not found on {file_path}")

        page = {}
        for key in meta:
            value = meta[key][0]
            # for post dates
            if re.search("^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2} [-+]\\d{4}$", value):
                page[key] = datetime.strptime(value, self.date_format)
            else:
                page[key] = value

        page["html"] = html

        return page

    ## Utils ##
    @staticmethod
    def load_config():
        text = Site.read_file(Site.config)
        return yaml.safe_load(text)

    @staticmethod
    def read_file(file_path):
        with open(file_path, "r", encoding=Site.encoding) as f:
            return f.read()

    @staticmethod
    def write_file(file_path, text):
        with open(file_path, "w", encoding=Site.encoding) as f:
            f.write(text)

    @staticmethod
    def write_config(config):
        Site.write_file(Site.config, yaml.safe_dump(config))

    @staticmethod
    def frontmatter(text):
        return f"---\n{yaml.safe_dump(text)}---\n"

    @staticmethod
    def get_date_str(tz):
        dt = datetime.now(ZoneInfo(tz))
        return dt.strftime(Site.date_format)

    @staticmethod
    def post():

        print("Initializing post...\n")

        config = Site.load_config()
        tz = config["tz"]

        post_path = input("Path: ") # from content
        post_title = input("Title: ")
        post_date = Site.get_date_str(tz)

        post = {
            "layout": "post",
            "title": post_title,
            "date": post_date
        }

        post_path = Site.content / post_path
        post_path.parent.mkdir(parents=True, exist_ok=True)
        Site.write_file(post_path, Site.frontmatter(post))

    @staticmethod
    def bootstrap():
        site_index = Site.content / "index.md"
        site_about = Site.content / "about.md"
        site_posts = Site.content / "posts"
        first_post = site_posts / "first-post.md"

        def tz_chooser():
            while True:
                choice = input("Time Zone: ")
                if re.search("[A-Z]{1}[a-z]+/[A-Z]{1}[a-z]+", choice):
                    return choice
                else:
                    print("Invalid time zone")

        def init_config():
            title = input("Title: ")
            description = input("Description: ")
            url = input("URL: ")
            author = input("Author: ")
            email = input("Email: ")
            tz = tz_chooser() # America/Chicago, etc

            config = {
                "title": title,
                "description": description,
                "url": url,
                "author": author,
                "email": email,
                "tz": tz,
                "feed": "post"
            }

            Site.write_config(config)

            return config

        def init_pages():
            index_text = {"layout": "home"}
            about_text = {"layout": "page", "title": "About"}
            Site.write_file(site_index, Site.frontmatter(index_text))
            Site.write_file(site_about, Site.frontmatter(about_text))

        def init_posts(config):
            site_posts.mkdir()
            text = {
                "layout": "post",
                "title": "First Post",
                "date": Site.get_date_str(config["tz"])
            }
            Site.write_file(first_post, Site.frontmatter(text))

        if not Site.content.exists():
            try:
                print("Initializing site...\n")
                Site.content.mkdir()
                config = init_config()
                init_pages()
                init_posts(config)
            except Exception:
                shutil.rmtree(Site.content, ignore_errors=True)
                raise
        else:
            print("Site already initialized. Skipping bootstrap.")


def main():
    parser = argparse.ArgumentParser(description="Website Builder")
    parser.add_argument("--post", action="store_true", help="Initialize a new post")
    parser.add_argument("--bootstrap", action="store_true", help="Bootstrap the site")
    args = parser.parse_args()

    if args.bootstrap:
        Site.bootstrap()
        return

    if args.post:
        Site.post()
        return

    site = Site()
    site.build()

if __name__ == "__main__":
    main()

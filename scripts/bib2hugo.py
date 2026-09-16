from pathlib import Path
import shutil
import re
import html
import bibtexparser


# ============================================================
# Configuration
# ============================================================

# Your master bibliography.
#
# This can be absolute:
BIB_FILE = Path(r"C:\Users\Matthias\resume\bibliography.bib")

# PhD thesis bibliography and Hugo output.
THESIS_BIB_FILE = Path(r"C:\Users\Matthias\resume\phd-thesis.bib")
THESIS_OUTPUT_DIR = Path("content/phd-thesis")

OUTPUT_DIR = Path("content/publications")



# ============================================================
# BibTeX helpers
# ============================================================

def field_value(entry, name):
    """
    Get a BibTeX field as a normal Python string.

    bibtexparser 2.x may return Field objects.
    """

    field = entry.get(name)

    if field is None:
        return ""

    if hasattr(field, "value"):
        return str(field.value)

    return str(field)


# ============================================================
# Text cleaning
# ============================================================

def clean_latex(text):
    """
    Clean common LaTeX/BibTeX syntax while preserving useful text.
    """

    if not text:
        return ""

    text = str(text).strip()

    replacements = {
        r"\&": "&",
        r"\%": "%",
        r"\_": "_",
        r"\#": "#",
        r"\$": "$",
        r"\{": "{",
        r"\}": "}",
        r"~": " ",
        "---": "—",
        "--": "–",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove protective BibTeX braces.
    text = text.replace("{", "").replace("}", "")

    # Collapse whitespace.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def yaml_escape(text):
    """
    Escape a string for a YAML double-quoted value.
    """

    if not text:
        return ""

    return (
        str(text)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )


def html_escape(text):
    """
    Escape text for HTML.
    """

    return html.escape(
        str(text),
        quote=True
    )


# ============================================================
# Author formatting
# ============================================================

def parse_authors(author_string):
    """
    Split a BibTeX author list.

    Example:

        Smith, John and Doe, Jane

    becomes:

        ["Smith, John", "Doe, Jane"]
    """

    if not author_string:
        return []

    return [
        clean_latex(author.strip())
        for author in re.split(
            r"\s+and\s+",
            author_string
        )
        if author.strip()
    ]


def format_author_siam(author):
    """
    Convert a BibTeX author to SIAM-style display format.

    Handles:

        Allard, Matthias
        Matthias Allard

    and produces:

        M. Allard
    """

    author = clean_latex(author).strip()

    if not author:
        return ""

    # --------------------------------------------------------
    # BibTeX "Last, First" format
    # --------------------------------------------------------

    if "," in author:

        parts = [
            p.strip()
            for p in author.split(",")
        ]

        last = parts[0]
        first = parts[1] if len(parts) > 1 else ""
        junior = parts[2] if len(parts) > 2 else ""

    # --------------------------------------------------------
    # "First Last" format
    # --------------------------------------------------------

    else:

        parts = author.split()

        if len(parts) == 1:
            return parts[0]

        last = parts[-1]
        first = " ".join(parts[:-1])
        junior = ""

    # --------------------------------------------------------
    # Convert first names to initials
    # --------------------------------------------------------

    initials = []

    for name in first.split():

        name = name.strip()

        if not name:
            continue

        name = name.strip(".")

        if name:
            initials.append(
                name[0].upper() + "."
            )

    # --------------------------------------------------------
    # Construct final name
    # --------------------------------------------------------

    if initials:

        result = (
            " ".join(initials)
            + " "
            + last
        )

    else:

        result = last

    if junior:
        result += ", " + junior

    return result


def format_authors_siam(authors):
    """
    Format all authors in SIAM-like style.
    """

    if not authors:
        return ""

    formatted = []

    has_others = False

    for author in authors:

        if author.lower() == "others":
            has_others = True
            continue

        formatted_author = format_author_siam(author)

        if formatted_author:
            formatted.append(formatted_author)

    if has_others:

        if formatted:
            return ", ".join(formatted) + ", et al."

        return "et al."

    if len(formatted) == 1:
        return formatted[0]

    if len(formatted) == 2:
        return (
            formatted[0]
            + " and "
            + formatted[1]
        )

    if len(formatted) > 2:
        return (
            ", ".join(formatted[:-1])
            + ", and "
            + formatted[-1]
        )

    return ""


# ============================================================
# Title formatting
# ============================================================

def format_title_siam(title):
    """
    Basic sentence-style title formatting.

    BibTeX capitalization protected by braces is already partly
    removed by clean_latex(), so we use a conservative approach.
    """

    title = clean_latex(title)

    if not title:
        return ""

    words = title.split()

    if not words:
        return title

    # Only convert obvious Title Case.
    if title == title.title():

        title = title.lower()

        title = (
            title[0].upper()
            + title[1:]
        )

    return title


# ============================================================
# Page formatting
# ============================================================

def normalize_pages(pages):
    """
    Normalize BibTeX page separators.
    """

    pages = clean_latex(pages)

    if not pages:
        return ""

    pages = pages.replace(
        "---",
        "–"
    )

    pages = pages.replace(
        "--",
        "–"
    )

    return pages


def format_pages_siam(pages):
    """
    Format pages as:

        123       -> p. 123
        123–145   -> pp. 123–145
        S1–S10    -> pp. S1–S10
    """

    pages = normalize_pages(pages)

    if not pages:
        return ""

    if (
        "–" in pages
        or "," in pages
        or "+" in pages
    ):
        return "pp. " + pages

    return "p. " + pages


# ============================================================
# Publication type
# ============================================================

def get_publication_type(entry_type):

    entry_type = entry_type.lower()

    if entry_type == "article":
        return "article-journal"

    if entry_type in (
        "inproceedings",
        "conference"
    ):
        return "paper-conference"

    if entry_type in (
        "phdthesis",
        "mastersthesis",
        "bachelorsthesis"
    ):
        return "thesis"

    if entry_type == "book":
        return "book"

    if entry_type in (
        "inbook",
        "incollection"
    ):
        return "chapter"

    if entry_type == "techreport":
        return "report"

    if entry_type == "patent":
        return "patent"

    return "article"


# ============================================================
# Citation HTML
# ============================================================

def get_raw_bibtex_entry(entry):
    """
    Return the original BibTeX entry as text.

    The citation key is preserved exactly.
    """

    try:
        return entry.raw
    except AttributeError:
        return str(entry)

def make_citation_html(entry):
    """
    Generate the citation stored in the Hugo front matter.

    Example:

        M. Allard. <em>Title</em>.
        Journal, <strong>58</strong> (2025), p. 215204.
        <a ...>doi</a>.
        <a ...>arXiv:2501.15765</a>.
    """

    entry_type = str(
        entry.entry_type
    ).lower()

    def get(field):
        return clean_latex(
            field_value(entry, field)
        ).strip()

    # --------------------------------------------------------
    # Authors
    # --------------------------------------------------------

    author_string = field_value(
        entry,
        "author"
    )

    authors = parse_authors(
        author_string
    )

    if not authors:

        authors = parse_authors(
            field_value(entry, "editor")
        )

    author_text = format_authors_siam(
        authors
    )

    author_text = html_escape(
        author_text
    )

    # --------------------------------------------------------
    # Fields
    # --------------------------------------------------------

    title = get("title")

    journal = get("journal")

    if not journal:
        journal = get("journaltitle")

    booktitle = get("booktitle")

    volume = get("volume")

    number = get("number")

    year = get("year")

    pages = get("pages")

    eid = get("eid")

    publisher = get("publisher")

    address = get("address")

    school = get("school")

    institution = get("institution")

    doi = get("doi")

    url = get("url")

    eprint = get("eprint")

    archive = get("archive").lower()

    archiveprefix = get(
        "archiveprefix"
    ).lower()

    note = get("note")

    # --------------------------------------------------------
    # arXiv detection
    # --------------------------------------------------------

    is_arxiv = (
        bool(eprint)
        and (
            archive == "arxiv"
            or archiveprefix == "arxiv"
        )
    )

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    title = format_title_siam(title)

    title_html = ""

    if title:

        title_html = (
            "<em>"
            + html_escape(title)
            + "</em>"
        )

    # --------------------------------------------------------
    # Publication name
    # --------------------------------------------------------

    if entry_type in (
        "inproceedings",
        "conference",
        "incollection",
        "inbook"
    ):

        publication = booktitle

    elif entry_type in (
        "phdthesis",
        "mastersthesis",
        "bachelorsthesis"
    ):

        publication = school

    elif entry_type == "techreport":

        publication = institution

    else:

        publication = journal

    publication_html = (
        html_escape(publication)
        if publication
        else ""
    )

    # --------------------------------------------------------
    # Start citation
    # --------------------------------------------------------

    parts = []

    if author_text:
        parts.append(
            author_text + "."
        )

    if title_html:
        parts.append(
            title_html + "."
        )

    # ========================================================
    # JOURNAL ARTICLE
    # ========================================================

    if entry_type == "article":

        if publication_html:

            journal_part = publication_html

            if volume:

                journal_part += (
                    ", <strong>"
                    + html_escape(volume)
                    + "</strong>"
                )

            if year:

                journal_part += (
                    " ("
                    + html_escape(year)
                    + ")"
                )

            parts.append(
                journal_part + "."
            )

        elif is_arxiv:

            arxiv_url = (
                "https://arxiv.org/abs/"
                + eprint
            )

            arxiv_text = (
                "arXiv:"
                + html_escape(eprint)
            )

            if year:

                arxiv_text += (
                    " ("
                    + html_escape(year)
                    + ")"
                )

            parts.append(
                '<a href="'
                + html_escape(arxiv_url)
                + '" target="_blank" '
                'rel="noopener">'
                + arxiv_text
                + "</a>."
            )

        elif year:

            parts.append(
                "("
                + html_escape(year)
                + ")."
            )

        # ----------------------------------------------------
        # Pages / article number
        # ----------------------------------------------------

        publication_pages = pages

        if not publication_pages and eid:
            publication_pages = eid

        if publication_pages:

            pages_text = normalize_pages(
                publication_pages
            )

            if (
                "–" in pages_text
                or "," in pages_text
                or "+" in pages_text
            ):

                parts.append(
                    "pp. "
                    + html_escape(pages_text)
                    + "."
                )

            else:

                parts.append(
                    "p. "
                    + html_escape(pages_text)
                    + "."
                )

    # ========================================================
    # BOOK
    # ========================================================

    elif entry_type == "book":

        if publication_html:
            parts.append(
                publication_html + "."
            )

        if volume:

            parts.append(
                "Vol. "
                + "<strong>"
                + html_escape(volume)
                + "</strong>."
            )

        if publisher:

            publisher_part = html_escape(
                publisher
            )

            if address:

                publisher_part += (
                    ", "
                    + html_escape(address)
                )

            parts.append(
                publisher_part + "."
            )

        if year:

            parts.append(
                "("
                + html_escape(year)
                + ")."
            )

        if pages:

            parts.append(
                "pp. "
                + html_escape(
                    normalize_pages(pages)
                )
                + "."
            )

    # ========================================================
    # BOOK CHAPTER
    # ========================================================

    elif entry_type in (
        "inbook",
        "incollection"
    ):

        if publication_html:

            parts.append(
                "In "
                + publication_html
                + "."
            )

        if publisher:

            parts.append(
                html_escape(publisher)
                + "."
            )

        if year:

            parts.append(
                "("
                + html_escape(year)
                + ")."
            )

        if pages:

            parts.append(
                "pp. "
                + html_escape(
                    normalize_pages(pages)
                )
                + "."
            )

    # ========================================================
    # CONFERENCE PAPER
    # ========================================================

    elif entry_type in (
        "inproceedings",
        "conference"
    ):

        if publication_html:

            parts.append(
                "In "
                + publication_html
                + "."
            )

        if publisher:

            parts.append(
                html_escape(publisher)
                + "."
            )

        if year:

            parts.append(
                "("
                + html_escape(year)
                + ")."
            )

        if pages:

            parts.append(
                "pp. "
                + html_escape(
                    normalize_pages(pages)
                )
                + "."
            )

    # ========================================================
    # PhD THESIS
    # ========================================================

    elif entry_type == "phdthesis":

        parts.append(
            "PhD thesis."
        )

        if publication_html:

            parts.append(
                publication_html + "."
            )

        if year:

            parts.append(
                "("
                + html_escape(year)
                + ")."
            )

    # ========================================================
    # Master's thesis
    # ========================================================

    elif entry_type == "mastersthesis":

        parts.append(
            "Master's thesis."
        )

        if publication_html:

            parts.append(
                publication_html + "."
            )

        if year:

            parts.append(
                "("
                + html_escape(year)
                + ")."
            )

    # ========================================================
    # Bachelor's thesis
    # ========================================================

    elif entry_type == "bachelorsthesis":

        parts.append(
            "Bachelor's thesis."
        )

        if publication_html:

            parts.append(
                publication_html + "."
            )

        if year:

            parts.append(
                "("
                + html_escape(year)
                + ")."
            )

    # ========================================================
    # Technical report
    # ========================================================

    elif entry_type == "techreport":

        parts.append(
            "Tech. Report."
        )

        if institution:

            parts.append(
                html_escape(institution)
                + "."
            )

        if year:

            parts.append(
                "("
                + html_escape(year)
                + ")."
            )

    # ========================================================
    # Other entry types
    # ========================================================

    else:

        if publication_html:

            parts.append(
                publication_html + "."
            )

        if year:

            parts.append(
                "("
                + html_escape(year)
                + ")."
            )

        if pages:

            parts.append(
                "pp. "
                + html_escape(
                    normalize_pages(pages)
                )
                + "."
            )

    # ========================================================
    # DOI
    # ========================================================

    if doi:

        doi_url = (
            "https://doi.org/"
            + doi
        )

        parts.append(
            '<a href="'
            + html_escape(doi_url)
            + '" target="_blank" '
            'rel="noopener">'
            "doi"
            "</a>."
        )

    # ========================================================
    # arXiv link
    # ========================================================

    if is_arxiv and publication_html:

        arxiv_url = (
            "https://arxiv.org/abs/"
            + eprint
        )

        parts.append(
            '<a href="'
            + html_escape(arxiv_url)
            + '" target="_blank" '
            'rel="noopener">'
            "arXiv:"
            + html_escape(eprint)
            + "</a>."
        )

    # ========================================================
    # Normal URL
    # ========================================================

    elif url and not is_arxiv:

        parts.append(
            '<a href="'
            + html_escape(url)
            + '" target="_blank" '
            'rel="noopener">'
            "link"
            "</a>."
        )

    # ========================================================
    # Note
    # ========================================================

    if note:

        parts.append(
            html_escape(note)
            + "."
        )

    # ========================================================
    # Final citation
    # ========================================================

    return " ".join(parts)


# ============================================================
# Hugo front matter
# ============================================================

def make_front_matter(entry):

    entry_type = str(
        entry.entry_type
    ).lower()

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Preserve the original BibTeX citation key.
    #
    # This is independent of DOI/arXiv/URL.
    #
    # Example:
    #
    #   @article{Allard2025HardEdge,
    #
    # becomes:
    #
    #   bibtex_key: "Allard2025HardEdge"
    #
    # --------------------------------------------------------

    bibtex_key = str(
        entry.key
    ).strip()

    bibtex_entry = get_raw_bibtex_entry(entry)


    # --------------------------------------------------------
    # Basic fields
    # --------------------------------------------------------

    title = clean_latex(
        field_value(entry, "title")
    )

    journal = clean_latex(
        field_value(entry, "journal")
    )

    if not journal:

        journal = clean_latex(
            field_value(entry, "journaltitle")
        )

    booktitle = clean_latex(
        field_value(entry, "booktitle")
    )

    abstract = clean_latex(
        field_value(entry, "abstract")
    )

    author_string = field_value(
        entry,
        "author"
    )

    authors = parse_authors(
        author_string
    )

    if not authors:

        authors = parse_authors(
            field_value(entry, "editor")
        )

    year = clean_latex(
        field_value(entry, "year")
    )

    if not year:
        year = "1900"

    volume = clean_latex(
        field_value(entry, "volume")
    )

    number = clean_latex(
        field_value(entry, "number")
    )

    pages = clean_latex(
        field_value(entry, "pages")
    )

    eid = clean_latex(
        field_value(entry, "eid")
    )

    publisher = clean_latex(
        field_value(entry, "publisher")
    )

    address = clean_latex(
        field_value(entry, "address")
    )

    school = clean_latex(
        field_value(entry, "school")
    )

    institution = clean_latex(
        field_value(entry, "institution")
    )

    doi = clean_latex(
        field_value(entry, "doi")
    )

    url = clean_latex(
        field_value(entry, "url")
    )

    eprint = clean_latex(
        field_value(entry, "eprint")
    )

    archive = clean_latex(
        field_value(entry, "archive")
    )

    archiveprefix = clean_latex(
        field_value(entry, "archiveprefix")
    )

    # --------------------------------------------------------
    # Publication name
    # --------------------------------------------------------

    if entry_type in (
        "inproceedings",
        "conference",
        "incollection",
        "inbook"
    ):

        publication = booktitle

    elif entry_type in (
        "phdthesis",
        "mastersthesis",
        "bachelorsthesis"
    ):

        publication = school

    elif entry_type == "techreport":

        publication = institution

    else:

        publication = journal

    # --------------------------------------------------------
    # Publication short name
    #
    # Use BibTeX shortjournal if available.
    # Otherwise leave empty.
    # --------------------------------------------------------

    short_name = clean_latex(
        field_value(entry, "shortjournal")
    )

    # --------------------------------------------------------
    # Publication type
    # --------------------------------------------------------

    publication_type = get_publication_type(
        entry_type
    )

    # --------------------------------------------------------
    # arXiv ID
    # --------------------------------------------------------

    if (
        eprint
        and (
            archive.lower() == "arxiv"
            or archiveprefix.lower() == "arxiv"
        )
    ):

        arxiv_id = eprint

    else:

        arxiv_id = ""

    # --------------------------------------------------------
    # Publication pages
    #
    # If there are no pages, use the electronic article ID.
    # --------------------------------------------------------

    publication_pages = pages

    if not publication_pages and eid:
        publication_pages = eid

    # --------------------------------------------------------
    # Citation
    # --------------------------------------------------------

    citation = make_citation_html(
        entry
    )

    # --------------------------------------------------------
    # Build YAML
    # --------------------------------------------------------

    lines = []

    lines.append("---")

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    lines.append(
        f'title: "{yaml_escape(title)}"'
    )

    # --------------------------------------------------------
    # BibTeX key
    #
    # IMPORTANT:
    # This is always written, even if there is no DOI.
    # --------------------------------------------------------

    lines.append(
        f'bibtex_key: "{yaml_escape(bibtex_key)}"'
    )

    # --------------------------------------------------------
    # Individual BibTeX entry
    # --------------------------------------------------------

    lines.append("bibtex: |")

    for bib_line in bibtex_entry.strip().splitlines():
        lines.append(
            f"  {bib_line}"
        )

    # --------------------------------------------------------
    # Authors
    # --------------------------------------------------------

    lines.append("authors:")

    if authors:

        for author in authors:

            formatted_author = (
                format_author_siam(author)
            )

            lines.append(
                f'  - "{yaml_escape(formatted_author)}"'
            )

    else:

        lines.append(
            '  - ""'
        )

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    lines.append(
        f'date: "{year}-01-01"'
    )

    lines.append(
        f'publishDate: "{year}-01-01"'
    )

    # --------------------------------------------------------
    # Publication type
    # --------------------------------------------------------

    lines.append(
        "publication_types:"
    )

    lines.append(
        f"  - {publication_type}"
    )

    # ========================================================
    # HugoBlox structured publication metadata
    # ========================================================

    lines.append("")
    lines.append("publication:")

    lines.append(
        f'  name: "{yaml_escape(publication)}"'
    )

    lines.append(
        f'  short_name: "{yaml_escape(short_name)}"'
    )

    lines.append(
        f'  volume: "{yaml_escape(volume)}"'
    )

    lines.append(
        f'  issue: "{yaml_escape(number)}"'
    )

    lines.append(
        f'  pages: "{yaml_escape(publication_pages)}"'
    )

    lines.append(
        f'  publisher: "{yaml_escape(publisher)}"'
    )

    # --------------------------------------------------------
    # Abstract
    # --------------------------------------------------------

    lines.append("")

    lines.append(
        f'abstract: "{yaml_escape(abstract)}"'
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary = (
        abstract
        if abstract
        else title
    )

    lines.append(
        f'summary: "{yaml_escape(summary)}"'
    )

    # --------------------------------------------------------
    # Citation
    # --------------------------------------------------------

    lines.append("")

    lines.append(
        f'citation: "{yaml_escape(citation)}"'
    )

    # --------------------------------------------------------
    # Tags
    # --------------------------------------------------------

    lines.append("")

    lines.append("tags:")

    lines.append(
        "  - Research"
    )

    # --------------------------------------------------------
    # Featured
    # --------------------------------------------------------

    lines.append("")

    lines.append(
        "featured: false"
    )

    # --------------------------------------------------------
    # HugoBlox identifiers
    #
    # Keep arXiv here.
    #
    # Also store the BibTeX key here so it is available through
    # the HugoBlox ID structure if needed.
    # --------------------------------------------------------

    lines.append("")

    lines.append("hugoblox:")

    lines.append("  ids:")

    lines.append(
        f'    arxiv: "{yaml_escape(arxiv_id)}"'
    )

    lines.append(
        f'    bibtex: "{yaml_escape(bibtex_key)}"'
    )

    # --------------------------------------------------------
    # Links
    #
    # DOI and normal URL remain normal publication links.
    #
    # BibTeX is NOT added as a fake URL because the BibTeX
    # button will retrieve the entry using bibtex_key.
    # --------------------------------------------------------

    lines.append("")

    lines.append("links:")

    if doi:

        lines.append(
            "  - type: doi"
        )

        lines.append(
            f'    url: "https://doi.org/{yaml_escape(doi)}"'
        )

    if url:

        lines.append(
            "  - type: url"
        )

        lines.append(
            f'    url: "{yaml_escape(url)}"'
        )

    # --------------------------------------------------------
    # Image
    # --------------------------------------------------------

    lines.append("")

    lines.append("image:")

    lines.append(
        '  caption: ""'
    )

    lines.append(
        '  focal_point: ""'
    )

    lines.append(
        "  preview_only: false"
    )

    # --------------------------------------------------------
    # Other Hugo fields
    # --------------------------------------------------------

    lines.append("")

    lines.append(
        "projects: []"
    )

    lines.append(
        'slides: ""'
    )

    lines.append(
        "draft: false"
    )

    # --------------------------------------------------------
    # End front matter
    # --------------------------------------------------------

    lines.append("---")
    lines.append("")

    lines.append(
        "<!-- Generated automatically from bibliography.bib. -->"
    )

    lines.append("")

    return "\n".join(lines)


# ============================================================
# Safe Hugo slug
# ============================================================

def make_slug(key):
    """
    Create a safe Hugo folder name from the BibTeX citation key.
    """

    slug = str(key).strip()

    slug = re.sub(
        r"[^A-Za-z0-9_-]+",
        "-",
        slug
    )

    slug = slug.strip("-")

    return slug

# ============================================================
# PhD Thesis
# ============================================================

def generate_phd_thesis():

    print()
    print("============================================")
    print(" PhD Thesis")
    print("============================================")
    print()

    # --------------------------------------------------------
    # Check thesis bibliography
    # --------------------------------------------------------

    if not THESIS_BIB_FILE.exists():

        print(
            f"WARNING: Thesis bibliography not found:\n"
            f"  {THESIS_BIB_FILE.resolve()}"
        )

        return

    print(
        f"Reading thesis bibliography:\n"
        f"  {THESIS_BIB_FILE.resolve()}"
    )

    # --------------------------------------------------------
    # Parse BibTeX
    # --------------------------------------------------------

    bib_text = THESIS_BIB_FILE.read_text(
        encoding="utf-8"
    )

    bib_database = bibtexparser.parse_string(
        bib_text
    )

    entries = bib_database.entries

    if not entries:

        print(
            "WARNING: No thesis entry found."
        )

        return

    # --------------------------------------------------------
    # We expect exactly one thesis entry.
    # --------------------------------------------------------

    entry = entries[0]

    print(
        f"Found thesis: {entry.key}"
    )

    # --------------------------------------------------------
    # Create output directory
    # --------------------------------------------------------

    THESIS_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print(
        f"Output directory:\n"
        f"  {THESIS_OUTPUT_DIR.resolve()}"
    )

    print()

    # --------------------------------------------------------
    # Generate citation using the SAME citation formatter
    # used by the publications.
    # --------------------------------------------------------

    citation = make_citation_html(entry)

    title = clean_latex(
        field_value(entry, "title")
    )

    year = clean_latex(
        field_value(entry, "year")
    )

    author_string = field_value(
        entry,
        "author"
    )

    authors = parse_authors(
        author_string
    )

    # --------------------------------------------------------
    # Generate Hugo front matter
    # --------------------------------------------------------

    lines = []

    lines.append("---")

    lines.append(
        f'title: "{yaml_escape(title)}"'
    )

    lines.append(
        f'bibtex_key: "{yaml_escape(str(entry.key))}"'
    )

    lines.append("authors:")

    for author in authors:

        formatted_author = format_author_siam(
            author
        )

        lines.append(
            f'  - "{yaml_escape(formatted_author)}"'
        )

    lines.append(
        f'date: "{year}-01-01"'
    )

    lines.append(
        f'publishDate: "{year}-01-01"'
    )

    lines.append("")

    lines.append(
        f'citation: "{yaml_escape(citation)}"'
    )

    lines.append("")

    lines.append("build:")

    lines.append(
        "  render: never"
    )

    lines.append(
        "  list: never"
    )

    lines.append("---")

    lines.append("")

    lines.append(
        "<!-- Generated automatically from phd-thesis.bib. -->"
    )

    lines.append("")

    output_file = (
        THESIS_OUTPUT_DIR / "index.md"
    )

    output_file.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    print(
        f"✓ Generated {output_file}"
    )

    print()

# ============================================================
# Main
# ============================================================

def main():

    print()
    print("============================================")
    print(" SIAM BibTeX → Hugo Blox")
    print("============================================")
    print()

    # --------------------------------------------------------
    # Check bibliography
    # --------------------------------------------------------

    if not BIB_FILE.exists():

        raise FileNotFoundError(
            "Could not find bibliography file:\n"
            f"{BIB_FILE.resolve()}"
        )

    print(
        f"Reading bibliography:\n"
        f"  {BIB_FILE.resolve()}"
    )

    # --------------------------------------------------------
    # Parse BibTeX
    # --------------------------------------------------------

    bib_text = BIB_FILE.read_text(
        encoding="utf-8"
    )

    bib_database = (
        bibtexparser.parse_string(
            bib_text
        )
    )

    entries = bib_database.entries

    print(
        f"Found {len(entries)} BibTeX entries."
    )

    # --------------------------------------------------------
    # Report parsing failures
    # --------------------------------------------------------

    if hasattr(bib_database, "failed_blocks"):

        failed_blocks = (
            bib_database.failed_blocks
        )

        if failed_blocks:

            print()
            print(
                "WARNING:"
            )

            print(
                f"  {len(failed_blocks)} BibTeX block(s) "
                "failed to parse."
            )

            for block in failed_blocks:

                print(
                    f"  - line {block.start_line}: "
                    f"{block.error}"
                )

            print()

    print()

    # --------------------------------------------------------
    # Rebuild output
    # --------------------------------------------------------

    if OUTPUT_DIR.exists():

        print(
            "Removing old generated publications:"
        )

        print(
            f"  {OUTPUT_DIR.resolve()}"
        )

        shutil.rmtree(
            OUTPUT_DIR
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Generate
    # --------------------------------------------------------

    generated = 0

    seen_keys = set()

    for entry in entries:

        if not entry.key:
            continue

        key = str(
            entry.key
        ).strip()

        # ----------------------------------------------------
        # Check duplicate keys
        # ----------------------------------------------------

        if key in seen_keys:

            print(
                f"WARNING: duplicate BibTeX key skipped: {key}"
            )

            continue

        seen_keys.add(key)

        # ----------------------------------------------------
        # Safe Hugo slug
        # ----------------------------------------------------

        slug = make_slug(
            key
        )

        if not slug:

            print(
                f"WARNING: could not create slug for key: {key}"
            )

            continue

        publication_dir = (
            OUTPUT_DIR / slug
        )

        publication_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        # ----------------------------------------------------
        # Generate front matter
        # ----------------------------------------------------

        content = make_front_matter(
            entry
        )

        output_file = (
            publication_dir / "index.md"
        )

        output_file.write_text(
            content,
            encoding="utf-8"
        )

        print(
            f"✓ {key}"
        )

        generated += 1

    # --------------------------------------------------------
    # Done
    # --------------------------------------------------------

    print()
    print("============================================")
    print(" Conversion complete")
    print("============================================")
    print()

    print(
        f"Generated {generated} publications."
    )

    print()

    print(
        f"Output directory:\n"
        f"  {OUTPUT_DIR.resolve()}"
    )

    print()

    print(
        "Each publication now contains its original "
        "BibTeX key in:"
    )

    print(
        "  bibtex_key:"
    )

    print()

    print(
        "Example:"
    )

    print(
        '  bibtex_key: "Allard2025HardEdge"'
    )

    print()


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":
    main()

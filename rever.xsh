from rever.activities.authors import Authors as ReverAuthors, update_metadata, eval_version, SORTINGS

class ConstructorAuthors(ReverAuthors):
    def _update_authors(self, filename, template, format, metadata, sortby, include_orgs):
        """helper function for updating / writing authors file"""
        md = update_metadata(metadata)
        template = eval_version(template)
        sorting_key, sorting_text = SORTINGS[sortby]
        md = sorted(md, key=sorting_key)
        if not include_orgs:
            md = [x for x in md if not x.get("is_org", False)]
        aformated = "".join([format.format(**x) for x in md])
        s = template.format(sorting_text=sorting_text, authors=aformated)
        s = s.rstrip() + "\n"
        # fixing an issue that is related to Unicode surrogates
        # (in one of the committer's names)
        with open(filename, 'w') as f:
            f.write(s.encode("utf-8", "surrogateescape").decode("utf-8", "replace"))
        return md


$DAG['authors'] = ConstructorAuthors()  # register the activity


$ACTIVITIES = [
    "authors",
    "changelog",
    # "tag",
    # "push_tag",
    # "ghrelease",
    # "conda_forge"
    ]

#
# Basic settings
#
$PROJECT = $GITHUB_REPO = "constructor"
$GITHUB_ORG = "conda"
$AUTHORS_FILENAME = "AUTHORS.md"
$AUTHORS_SORTBY = "alpha"

#
# Changelog settings
#
$CHANGELOG_FILENAME = "CHANGELOG.md"
$CHANGELOG_PATTERN = r"\[//\]: # \(current developments\)"
$CHANGELOG_HEADER = """[//]: # (current developments)

## $RELEASE_DATE   $VERSION:
"""
$CHANGELOG_CATEGORIES = (
    "Enhancements",
    "Bug fixes",
    "Deprecations",
    "Docs",
    "Other",
)
$CHANGELOG_CATEGORY_TITLE_FORMAT = '### {category}\n\n'

$CHANGELOG_AUTHORS_TITLE = "Contributors"
$CHANGELOG_AUTHORS_FORMAT = "* @{github}\n"

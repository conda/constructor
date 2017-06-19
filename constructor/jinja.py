from jinja2 import BaseLoader, Environment, FileSystemLoader, TemplateError

from constructor.exceptions import UnableToParse


# adapted from conda-build
class FilteredLoader(BaseLoader):
    """
    A pass-through for the given loader, except that the loaded source is
    filtered according to any metadata selectors in the source text.
    """

    def __init__(self, unfiltered_loader, content_filter):
        self._unfiltered_loader = unfiltered_loader
        self.list_templates = unfiltered_loader.list_templates
        self.content_filter = content_filter

    def get_source(self, environment, template):
        loader = self._unfiltered_loader
        contents, filename, uptodate = loader.get_source(environment, template)
        filtered_contents = self.content_filter(contents)
        return filtered_contents, filename, uptodate


# adapted from conda-build
def render_jinja(data, directory, content_filter):
    loader = FilteredLoader(FileSystemLoader(directory), content_filter)
    env = Environment(loader=loader)
    try:
        template = env.from_string(data)
        rendered = template.render()
    except TemplateError as ex:
        raise UnableToParse(original=ex)
    return rendered

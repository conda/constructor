from jinja2 import Environment, TemplateError

from constructor.exceptions import UnableToParse

# adapted from conda-build
def render_jinja(data):
    env = Environment()
    try:
        template = env.from_string(data)
        rendered = template.render()
    except TemplateError as ex:
        raise UnableToParse(original=ex)
    return rendered

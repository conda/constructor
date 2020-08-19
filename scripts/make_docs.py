import jinja2
import sys
from os.path import join, dirname

REPO_ROOT = dirname(dirname(__file__))

sys.path.insert(0, REPO_ROOT)

from constructor import construct


valid_platforms = construct.ns_platform(sys.platform)

template = """
# The `construct.yaml` specification

The `construct.yaml` file is the primary mechanism for controlling
the output of the Constructor package. The file contains a list of
key/value pairs in the standard [YAML](https://yaml.org/) format.
Each configuration option is listed in its own subsection below.

Constructor employs the Selector enhancement of the YAML format
first employed in the
[conda-build](https://docs.conda.io/projects/conda-build/en/latest/)
project. Selectors are specially formatted YAML comments that Constructor
uses to customize the specification for different platforms. The precise
syntax for selectors is described in
[this section](https://docs.conda.io/projects/conda-build/en/latest/resources/define-metadata.html#preprocessing-selectors)
of the `conda-build` documentation. The list of selectors available
for use in Constructor specs is given in the section
[Available selectors](#Available-selectors) below.

{% for key_info in keys %}
## `{{key_info[0]}}`

_required:_ {{key_info[1]}}<br/>
_type{{key_info[4]}}:_ {{key_info[2]}}<br/>{{key_info[3]}}{% endfor %}

## Available selectors
{% for key, val in platforms|dictsort %}
- `{{key}}`{% endfor %}
"""

key_info_list = []
for key_info in construct.KEYS:
    type_names = {str: 'string', list: 'list', dict: 'dictionary', bool: 'boolean'}
    key_types = key_info[2]
    if not isinstance(key_types, (tuple, list)):
        key_types = key_types,
    plural = 's' if len(key_types) > 1 else ''
    key_types = ', '.join(type_names.get(k, '') for k in key_types)
    required = 'yes' if key_info[1] else 'no'

    if key_info[3] == 'XXX':
        print("Not including %s because the skip sentinel ('XXX') is set" % key_info[0])
        continue

    key_info_list.append((key_info[0], required, key_types, key_info[3], plural))

output = jinja2.Template(template).render(
    platforms=valid_platforms,
    keys=key_info_list)

with open(join(REPO_ROOT, 'CONSTRUCT.md'), 'w') as f:
    f.write(output)
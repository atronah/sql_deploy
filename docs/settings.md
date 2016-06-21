.ini file structure
===================

.ini file with deploy settings consists of sections (e.g. `[rule1]`, `[rule2]`), which describes rules for deploying.
Note, that section `[general]` describes default rule, the settings of which are applied to the others rules, if this settings are not explicitly overriden by them.

Each rule consists of some pairs `parameter=value`. The most of pairs describe values, that will be substitute instead of constructions `{<parameter_name>}`, where *parameter_name* is name of parameter from rule section. In other words, if rule contains pair `my_param = my_value`, during deploy string `{my_param}` in all scripts of this rule (and dependents rules) will be substitute by string `my_value`. But, there are some special reserved parameters:
* `sources` - defines rules and\or names of files with sql queries (as list, separated by comma or line break), that have to be concatinated to single deploy result script in specified order.
* `directory` - defines directory, in which to look for files, specified in `sources` parameter.

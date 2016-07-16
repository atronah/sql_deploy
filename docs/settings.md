Settings file
=============

Settings file is the [INI file][] file, which contains following information to compile result deploy script:
* Ordered lists of source files, grouped into rules. 
* Parameters for customizing source files (by substituting values of parameters into the source files).
* Options for compiling process
 
Base entity of settings file is rule.

Rule is the INI file section, which are beginning with name in square brackets and ending with the next section declaration or end of file.
Each rule contains ini properties, which define one of following things:
* Ordered list of sources (parameter with reserved name `_sources`). Each source can be either a file name or another rule.
* Compile options (properties with reserved name):
    * `_workdir` - defines directory, in which to look for files, specified in `_sources` parameter.
* User parameters with arbitrary names (except reserved) to customize source files.

_Note_: `[general`] section is required and used for defining global default parameters. 
If you don't specify rule name(-s) in command line arguments during run compile.py, 
this section will be used as default rule. 

[Example settings file](../example_settinfs.ini)
 
[^1]: pair `key=value`, `value` can span multiple lines if this lines started with whitespace symbols
*[INI]: initialization
[INI file]: https://en.wikipedia.org/wiki/INI_file


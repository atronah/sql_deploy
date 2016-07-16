Description
============
Compiles separated sql scripts (procedures, tables, triggers etc) into single sql-script to execute all queries in correct order.

Parse comments
==============


Compile settings
================

All settings of compile process stored in [Settings file](docs/settings.md)



Supported special commands
--------------------------
* `\fn <name>`, `\tb <name>`, `\mg <name>`, `\sq <name>`
* `\brief <multi-line text until blank line or nex command>`
* `\md <path to md file>`
* `\param`, `\param[in]`, `\param[out]`

Before this porject was a part of [fbTools](http://gitlab.com/mplus/fbTools) project (until SHA1 `2c580115aa9a38f1bfa85bd0fa556631d9a5cda9`)

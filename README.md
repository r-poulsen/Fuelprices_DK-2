# Fuelprices DK²

## Introduction

A fork of [J-Lindvig](https://github.com/J-Lindvig/)'s most excellent [Fuelprices DK](https://github.com/J-Lindvig/Fuelprices_DK), with a couple of fixes, an additional company and hopefully a higher degree of fault-tolerance.

## Installation

### HACS

Add the custom repo https://github.com/r-poulsen/Fuelprices_DK-2 and install from there.

## Configuration

In the default configuration it will track the following fueltypes:

-   Octane 95
-   Octane 95+ (additives)
-   Octane 100
-   Diesel
-   Diesel+ (additives)
-   Charger
-   Quickcharger

From these fuelcompanies:

-   Circle K
-   F24
-   Go'On
-   ingo
-   OIL! tank & go
-   OK
-   Q8
-   Shell
-   Uno-X

## Configuration

```yaml
fuelprices_dk-2:
    # Optional entries
    # Bypass the default update interval (60 minutes)
    update_interval: 300
    companies:
        # possible values are: circlek, f24, goon, ingo, oil, ok, q8, shell and unox
        - ok
        - shell
    fueltypes:
        # Possible values are: oktan 95, oktan 95+, oktan 100, diesel, diesel+, charge and quickcharge
        - oktan 95
        - diesel
```

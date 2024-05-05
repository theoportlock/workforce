---
title: "Workforce"
author:
  - Theo Portlock\inst{1}
  - Justin O'Sullivan\inst{1}
institute:
  - \inst{1}The University of Auckland
date: 03-04-2024
output:
  beamer_presentation:
    theme: "Madrid"
    colortheme: "dolphin"
    fonttheme: "structurebold"
---

# Science

# Science
* Repeatablilty

# Requirements of reproducibility
* Easy to run/use
    * Good documentation
    * Detailed methods (version control)
    * Multiple platforms/OS
    * Cheap - maximises resources
    * Scaleable - as datasets get bigger, this becomes more important
* Easy to understand - (also makes it easier to upgrade)
    * Good tutorials
* Easy to troubleshoot/test
    * Able to resume from previous steps
    * Errors are clear
* Good data hygeine

# Nextflow
* Pipeline writing language
* Nf-core
* Sequera - Phil Ewels
* Meets *most* of these requirements
* Containerised, version controlled, and can run on multiple platforms 
* Steep learning curve

# Nextflow
![](figures/nextflow.pdf){ width=50% }

# Nextflow
![](figures/nfmag.pdf)

# Downstream analysis
* 12,000 line R script, python file, or SPSS file
* Collection of random CUSTOM scripts released on github
* Slow
* Often difficult to install correct versions of packages
* Documentation limited to README or methods section, often split between
* Only run on one platform/OS
* ALL THE SAME REQUIREMENTS APPLY!

# Workforce
![](figures/anotherex.pdf)

# Workforce
* A DCG (Directed Cyclic graph) based pipeline designer for downstream analysis
* Installed with 'pip install workforce'
* Integrates into existing tools
* Uses less code
* Process tracking
* Install with pip on any operating system
* Can run over multiple servers in parallel
* Leans on existing command line commands
* Simple interface
* Can interact with a run while it's still running
* Collaberative development

# Workforce
* networkx
* subprocess
* multiprocessing
* dash cytoscape

# Workforce - case study
![](figures/alldata.pdf){ width=80% }

# Workforce - case study
![](figures/ex2.pdf)

# Workforce - case study
![](figures/ex3.pdf){ width=80% }

# Workforce - case study
![](figures/ex4.pdf){ width=80% }

# Future work
* Continuous workflows for data recording

# Final thoughts
* Workforce is a pipeline designer for downstream analysis
* It runs processes in parallel and across servers
* Much more testing is required!


#!/bin/bash
rm -rf tmp/*
#exclude pyc
# tree BackEnd > tmp/BackEnd_tree.txt
tree BackEnd -I "*.pyc" > tmp/BackEnd_tree.txt
tree FrontEnd/src > tmp/FrontEnd_src_tree.txt
find BackEnd -name "*.py" | xargs cp -t tmp/
find FrontEnd/src -type f | xargs cp -t tmp/
cp FrontEnd/src/store/index.ts tmp/FrontEnd_src_store_index.ts

#!/bin/bash

echo "Here are the arguments: $@"

while getopts 'a:b:c:' OPTION; do
        case $OPTION in
                a) A="$OPTARG" ;;
                b) B="$OPTARG" ;;
                c) C="$OPTARG" ;;
        \?)
                echo "Invalid option: -$OPTARG" 
                exit 1
        ;;
        :)
                echo "Option -$OPTARG requires an argument." 
                exit 1
        ;;
        esac
done
shift $(($OPTIND - 1))

echo 'hello world'

echo "A: $A"
echo "B: $B"
echo "C: $C"

echo badger

exit 42 

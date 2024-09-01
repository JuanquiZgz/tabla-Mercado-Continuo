#!/bin/bash
day_of_month=$(date +%d)
if [ "$day_of_month" -le 07 ]; then
  git config --global user.email "jczaragoza@hotmail.es"
  git config --global user.name "JuanquiZgz"
  git commit --allow-empty -m "Mantener actividad"
  git push
else
  echo "No es el primer domingo del mes, no se realizará ningún commit."
fi
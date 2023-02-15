#!/bin/bash
git config --global user.email "robot-irt-jenkins@yandex-team.ru"
git config --global user.name "robot-irt-jenkins"

git diff
git add *.java
git_status=$(git status | grep 'nothing to commit')
echo $git_status

if [[ $git_status == "" ]]; then
   echo "imported tests found"
   git commit -m "testpalm set-id"
   git push origin HEAD:$BRANCH_NAME
else
   echo "imported tests NOT found"
fi
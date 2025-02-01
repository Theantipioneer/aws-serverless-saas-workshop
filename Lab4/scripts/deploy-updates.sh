#!/bin/bash
cd ../server || exit # stop execution if cd fails
rm -rf .aws-sam/
python3 -m pylint -E -d E0401 $(find . -iname "*.py" -not -path "./.aws-sam/*")
  if [[ $? -ne 0 ]]; then
    echo "****ERROR: Please fix above code errors and then rerun script!!****"
    exit 1
  fi
#Deploying shared services changes
echo "Deploying business services changes" 
# echo Y | sam sync --stack-name stack-pooled --code --resource-id GetExpenseAnalysisFunction -u --template tenant-template.yaml
# echo Y | sam sync --stack-name stack-pooled --code --resource-id AnalyseExpenseFunction -u --template tenant-template.yaml
# echo Y | sam sync --stack-name stack-pooled --code --resource-id ServerlessSaaSLayers -u --template tenant-template.yaml
echo Y | sam sync --stack-name stack-pooled --code --resource-id UploadFunction -u --template tenant-template.yaml
# echo Y | sam sync --stack-name acumen-saas --code --resource-id LambdaFunctions/UpdateBalanceFunction -u --template shared-template.yaml
# echo Y | sam sync --stack-name acumen-saas --code --resource-id LambdaFunctions/GetBalanceFunction -u --template shared-template.yaml
# echo Y | sam sync --stack-name acumen-saas --code --resource-id LambdaFunctions/SharedServicesAuthorizerFunction -u --template shared-template.yaml
# echo Y | sam sync --stack-name stack-pooled --code --resource-id BusinessServicesAuthorizerFunction -u --template tenant-template.yaml

cd ../scripts || exit
echo "Completed updates for lab4 business services"
# ./geturl.sh
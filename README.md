# Building DLL  

## Open a PowerShell window and type:  

wsl --install Ubuntu  

## In Ubuntu terminal:  

\# run these once  
mkdir ~/tools  
cd tools  
curl -L -O https://github.com/mstorsjo/llvm-mingw/releases/download/20261020/llvm-mingw-20261020-ucrt-ubuntu-22.04-x86_64.tar.xz  
tar -xf llvm-mingw-20261020-ucrt-ubuntu-22.04-x86_64.tar.xz
mv llvm-mingw-20261020-ucrt-ubuntu-22.04-x86_64 llvm-mingw  



\# run these whenever building the mod  

\# if SC4Speeding folder is on Windows Desktop  
cd /mnt/c/Users/**username**/Desktop/SC4Speeding/source/  

export SC4_LLVM_ROOT="$HOME/tools/llvm-mingw"  
bash build.sh  

## DLL location  
SC4Speeding\source\build\SC4Speeding.dll  

# Creating DAT files  

\# run these once  
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/master/install.sh | bash  
npm install --lts  
\# exit and re-enter WSL Ubuntu terminal  
npm install node  
npm install -g sc4  

sudo apt update  
sudo apt install python3-pil  

\# create a folder named game-data in SC4Speeding, place SimCity_1.dat from SimCity4 installation directory there  
\# copy speeding-gauge.png from SC4Speeding/source/ui/ to SC4Speeding/native-plugin/ui and SC4Speeding/native-plugin/build  

\# run these whenever creating the ordinance, in SC4Speeding/source  
export SC4_LIBRARY_ROOT=$(npm root -g)/sc4  
python3 ./make_ordinance.py  

\# run these whenever creating the UI, in SC4Speeding/source/ui  
python3 ./build_ui.py  

\# run these whenever creating the data, must run build_ui first  
\# copy speeding-marker.resource from SC4Speeding/native-plugin/build to SC4Speeding/source/build  
python3 ./make_data.py  

## Dat file locations  
SC4Speeding\source\build\SC4Speeding.dat  
SC4Speeding\native-plugin\build\SC4Speeding-CrimeUI.dat  
SC4Speeding\source\build\140-ordinances\SC4Speeding-SpeedTraps.dat  
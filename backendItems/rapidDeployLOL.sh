rm -rf sfOrinMonitoring/
sudo rm /etc/systemd/system/dismalOrinGather.service
git clone https://github.com/dismalict/sfOrinMonitoringV2.git
cd sfOrinMonitoringV2/backendItems/ && sudo chmod +x install_dependencies.sh

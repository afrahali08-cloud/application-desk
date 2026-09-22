chrome.action.onClicked.addListener(async tab => {
  await chrome.windows.create({url:chrome.runtime.getURL('panel.html')+'?source='+tab.id,type:'popup',width:500,height:660});
});

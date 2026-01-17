// Этот скрипт работает в фоне и связывает кнопку с панелью

// Разрешаем открытие панели по клику на иконку расширения
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error(error));

chrome.action.onClicked.addListener((tab) => {
  // На всякий случай дублируем открытие (для старых версий Chrome)
  chrome.sidePanel.open({ windowId: tab.windowId });
});
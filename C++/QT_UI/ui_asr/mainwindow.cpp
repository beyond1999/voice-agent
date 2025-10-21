#include "mainwindow.h"
#include <QTimer>
#include "./ui_mainwindow.h"

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , ui(new Ui::MainWindow)
{
    ui->setupUi(this);
    // 1. 连接侧边栏折叠按钮
    connect(ui->toggleButton, &QPushButton::clicked, this, &MainWindow::onToggleButtonClicked);

    // 2. 连接菜单按钮以切换页面
    connect(ui->mainMenuButton, &QPushButton::clicked, this, &MainWindow::onMainMenuButtonClicked);
    connect(ui->settingsMenuButton, &QPushButton::clicked, this, &MainWindow::onSettingsMenuButtonClicked);
    // ⭐ 连接麦克风按钮的 clicked 信号到新的槽函数
    connect(ui->micButton, &QPushButton::pressed, this, &MainWindow::onMicButtonPressed);
    connect(ui->micButton, &QPushButton::released, this, &MainWindow::onMicButtonReleased);
    // --- 初始状态设置 ---

    // 程序启动时，默认显示主界面 (索引为 0)
    ui->mainStackedWidget->setCurrentIndex(0);
}

MainWindow::~MainWindow()
{
    delete ui;
}
void MainWindow::onMainMenuButtonClicked()
{
    // QStackedWidget 使用索引来切换页面，我们在Designer里创建的页面顺序就是索引顺序
    // mainPage 是第一个，所以索引是 0
    ui->mainStackedWidget->setCurrentIndex(0);
}

void MainWindow::onSettingsMenuButtonClicked()
{
    // settingsPage 是第二个，所以索引是 1
    ui->mainStackedWidget->setCurrentIndex(1);
}

void MainWindow::onToggleButtonClicked()
{
    // 检查侧边栏当前是否可见
    if (ui->sidebarWidget->isVisible()) {
        ui->sidebarWidget->hide(); // 如果可见，就隐藏它
        ui->toggleButton->setText(">"); // 更新按钮文本
    } else {
        ui->sidebarWidget->show(); // 如果不可见，就显示它
        ui->toggleButton->setText("<"); // 恢复按钮文本
    }
}

void MainWindow::onMicButtonPressed()
{
    // 改变按钮外观以提供反馈
    ui->micButton->setText("正在聆听...");

    // (未来) 在这里调用核心逻辑来真正开始录音
    // appController->startListening();
    qDebug() << "鼠标按下，开始聆听...";
}

// ⭐ 实现鼠标松开时的逻辑
void MainWindow::onMicButtonReleased()
{
    // 恢复按钮外观
    ui->micButton->setText("开始聆听");

    // (未来) 在这里调用核心逻辑来停止录音
    // appController->stopListening();
    qDebug() << "鼠标松开，停止聆听。";
}

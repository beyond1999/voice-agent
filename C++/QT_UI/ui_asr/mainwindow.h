#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>

QT_BEGIN_NAMESPACE
namespace Ui {
class MainWindow;
}
QT_END_NAMESPACE

class MainWindow : public QMainWindow
{
    Q_OBJECT

private slots:
    //  用于切换到不同页面的槽
    void onMainMenuButtonClicked();
    void onSettingsMenuButtonClicked();

    //  用于折叠/展开侧边栏的槽
    void onToggleButtonClicked();
    void onMicButtonPressed();
    void onMicButtonReleased();

public:
    MainWindow(QWidget *parent = nullptr);
    ~MainWindow();

private:
    Ui::MainWindow *ui;
};
#endif // MAINWINDOW_H

#!/bin/bash
# Paperang P1 树莓派一键更新脚本
# 拉取最新代码并重启服务；服务启动失败时自动回滚到上一版本
# 使用方法: bash update_raspberrypi.sh 或 ./update_raspberrypi.sh

INSTALL_DIR="/home/pi/paperang-p1"
UPDATED=0   # 是否发生了代码更新（用于决定失败时是否回滚）

echo "======================================"
echo "Paperang P1 树莓派一键更新"
echo "======================================"

# 1. 进入项目目录
cd "$INSTALL_DIR" || {
    echo "[错误] 项目目录不存在: $INSTALL_DIR"
    exit 1
}
echo "[1/4] 进入项目目录: $(pwd)"

# 2. 拉取最新代码
echo "[2/4] 拉取最新代码..."

# 确认当前是 git 仓库
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "[错误] 当前目录不是有效的 git 仓库: $(pwd)"
    exit 1
fi

# 拉取远程更新；失败说明网络不通，直接退出避免误判
if ! git fetch origin 2>&1; then
    echo "[错误] git fetch 失败，无法连接远程仓库，请检查网络后重试"
    exit 1
fi

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/master 2>/dev/null) || {
    echo "[错误] 无法获取远程分支 origin/master 信息，请检查仓库远程配置"
    exit 1
}

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "  当前已是最新版本: ${LOCAL:0:7}"
    echo "  仍要继续重启服务吗？(y/N)"
    read -r ANSWER
    if [ "$ANSWER" != "y" ] && [ "$ANSWER" != "Y" ]; then
        echo "已取消，未重启服务。"
        exit 0
    fi
else
    echo "  本地: ${LOCAL:0:7}"
    echo "  远程: ${REMOTE:0:7}"
    # 检测本地是否有未提交改动（含 untracked 文件）
    if ! git diff --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
        echo "  检测到本地有未提交改动，暂存后拉取..."
        # 使用 -u 同时暂存 untracked 文件，避免拉取时被远程同名文件覆盖而冲突
        if git stash push -u -m "auto-stash before pull" 2>/dev/null; then
            STASHED=1
        else
            STASHED=0
            echo "  [警告] stash 暂存失败，尝试直接拉取..."
        fi
    else
        STASHED=0
    fi

    # 执行拉取（--ff-only 只允许快进合并，避免在树莓派上生成合并提交）
    if git pull --ff-only origin master; then
        echo "  更新完成: $(git rev-parse --short HEAD)"
    else
        echo ""
        echo "[错误] git pull 失败，代码未更新！"
        # 拉取失败时恢复暂存的改动
        if [ "$STASHED" = "1" ]; then
            echo "  正在恢复暂存的改动..."
            git stash pop || echo "  [警告] 恢复失败，改动保存在 stash 中（git stash list 查看）"
        fi
        echo "  可能原因:"
        echo "    1. 本地改动与远程代码冲突"
        echo "    2. 网络连接问题"
        echo "  请处理后重新运行本脚本。"
        exit 1
    fi
    # 拉取成功后恢复暂存的改动
    if [ "$STASHED" = "1" ]; then
        echo "  恢复暂存的本地改动..."
        if ! git stash pop; then
            echo ""
            echo "[错误] 恢复本地改动时发生冲突，代码处于不完整状态！"
            echo "  请手动处理: git status / git stash list，解决后重新运行本脚本。"
            exit 1
        fi
    fi
    UPDATED=1
fi

# 3. 同步依赖（若 requirements.txt 有变化）
echo "[3/4] 检查依赖..."
if [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
    if pip install --index-url https://www.piwheels.org/simple/ -r requirements.txt -q; then
        echo "  依赖已同步"
    else
        echo "  [警告] 依赖安装失败，服务可能无法正常启动（将尝试自动回滚）"
    fi
else
    echo "  [提示] 未找到 venv，跳过依赖安装（请先运行 setup_raspberrypi.sh）"
fi

# 4. 重启服务（启动失败时自动回滚到上一版本）
echo "[4/4] 重启服务..."
sudo systemctl restart paperang-rfcomm.service
sleep 1
sudo systemctl restart paperang-web.service
sleep 2

# 检查服务状态
WEB_STATUS=$(systemctl is-active paperang-web.service)
RFCOMM_STATUS=$(systemctl is-active paperang-rfcomm.service)
echo "  paperang-rfcomm: $RFCOMM_STATUS"
echo "  paperang-web   : $WEB_STATUS"

# 回滚函数：将代码恢复到更新前的版本并重启服务
rollback() {
    echo ""
    echo "[回滚] 正在回滚到上一个版本: ${LOCAL:0:7}"
    # 先暂存当前本地改动（含 untracked），避免回滚时丢失
    if ! git diff --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
        if git stash push -u -m "auto-stash before rollback" 2>/dev/null; then
            ROLLBACK_STASHED=1
        else
            ROLLBACK_STASHED=0
            echo "  [警告] 回滚前暂存本地改动失败，未提交的改动可能丢失"
        fi
    else
        ROLLBACK_STASHED=0
    fi
    git reset --hard "$LOCAL" || {
        echo "  [错误] 回滚失败，请手动执行: git reset --hard ${LOCAL:0:7}"
        exit 1
    }
    if [ "$ROLLBACK_STASHED" = "1" ]; then
        git stash pop || echo "  [警告] 回滚后本地改动恢复冲突，请手动处理: git stash list"
    fi
    echo "  已回滚到: $(git rev-parse --short HEAD)"
    echo "  正在重启服务..."
    sudo systemctl restart paperang-rfcomm.service
    sleep 1
    sudo systemctl restart paperang-web.service
    sleep 2
}

if [ "$WEB_STATUS" != "active" ]; then
    echo ""
    echo "[警告] paperang-web 服务启动失败！"
    if [ "$UPDATED" = "1" ]; then
        rollback
        if [ "$(systemctl is-active paperang-web.service)" = "active" ]; then
            echo ""
            echo "======================================"
            echo "已自动回滚到上一版本: $(git rev-parse --short HEAD)"
            echo "访问: http://$(hostname -I | awk '{print $1}'):5000"
            echo "======================================"
            exit 0
        fi
        echo ""
        echo "[错误] 回滚后服务仍无法启动，请查看日志："
        echo "  sudo journalctl -u paperang-web.service -n 30 --no-pager"
        exit 1
    fi
    echo "  本次未更新代码，无旧版本可回滚，请查看日志："
    echo "  sudo journalctl -u paperang-web.service -n 30 --no-pager"
    exit 1
fi

if [ "$RFCOMM_STATUS" != "active" ]; then
    echo ""
    echo "[警告] paperang-rfcomm 服务未正常运行（不影响网页访问）"
    echo "  查看日志: sudo journalctl -u paperang-rfcomm.service -n 30 --no-pager"
fi

echo ""
echo "======================================"
echo "更新成功！"
echo "当前版本: $(git rev-parse --short HEAD)"
echo "访问: http://$(hostname -I | awk '{print $1}'):5000"
echo "======================================"

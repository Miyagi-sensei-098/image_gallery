function checkPassword() {
    const password = "team_masa"; // ここにパスワードを設定
    const input = prompt("パスワードを入力してね★:");
    if (input !== password) {
        document.body.innerHTML = '<div style="text-align:center;margin-top:50px;font-family:Arial, sans-serif;"><h1>残念。アクセスが拒否されました</h1><p>正しいパスワードを入力してね★</p><p><a href="javascript:location.reload()">再試行</a></p></div>';
    }
}
window.onload = checkPassword;
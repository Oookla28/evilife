package com.evilife.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalContext
import androidx.health.connect.client.HealthConnectClient
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.coroutines.launch
import java.util.UUID

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); setContent { EviLifeApp(Api(this)) } }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun EviLifeApp(api: Api) {
    val scope = rememberCoroutineScope(); var tab by remember { mutableStateOf(0) }; var email by remember { mutableStateOf("") }; var password by remember { mutableStateOf("") }; var logged by remember { mutableStateOf(false) }; var status by remember { mutableStateOf("") }; var question by remember { mutableStateOf("") }; val answers = remember { mutableStateListOf<String>() }
    val scanner = rememberLauncherForActivityResult(ScanContract()) { result -> result.contents?.let { code -> scope.launch { status = try { api.claim(code); "配对成功，已绑定网页账号" } catch (e: Exception) { e.message ?: "配对失败" } } } }
    val context = LocalContext.current
    val health = remember { HealthSync(context, api) }
    val permissions = rememberLauncherForActivityResult(HealthConnectClient.getOrCreate(context).permissionController.createRequestPermissionResultContract()) { granted -> if (granted.containsAll(health.permissions)) scope.launch { status = try { health.sync(); "健康数据已同步" } catch (e: Exception) { e.message ?: "同步失败" } } else status = "未获得所需健康权限" }
    MaterialTheme(colorScheme = lightColorScheme(primary = Color(0xFF0F766E), secondary = Color(0xFF14B8A6))) {
        Scaffold(topBar = { TopAppBar(title = { Text("EviLife") }) }, bottomBar = { NavigationBar { listOf("问答", "健康", "设置").forEachIndexed { i, label -> NavigationBarItem(selected = tab == i, onClick = { tab = i }, icon = { Text(listOf("⌂", "♡", "⚙")[i]) }, label = { Text(label) }) } } }) { padding ->
            Column(Modifier.padding(padding).padding(20.dp).fillMaxSize(), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                if (!logged) { Text("登录 EviLife", style = MaterialTheme.typography.headlineSmall); OutlinedTextField(email, { email = it }, label = { Text("邮箱") }, modifier = Modifier.fillMaxWidth()); OutlinedTextField(password, { password = it }, label = { Text("密码") }, modifier = Modifier.fillMaxWidth()); Button(onClick = { scope.launch { status = try { api.login(email, password); logged = true; "登录成功" } catch (e: Exception) { e.message ?: "登录失败" } } }, modifier = Modifier.fillMaxWidth()) { Text("登录") }; Text(status) }
                else when (tab) {
                    0 -> { Text("循证问答", style = MaterialTheme.typography.headlineSmall); OutlinedTextField(question, { question = it }, label = { Text("想问什么？") }, modifier = Modifier.fillMaxWidth(), minLines = 3); Button(onClick = { if (question.isNotBlank()) scope.launch { status = "正在分析…"; try { answers.add(api.orchestrate(UUID.randomUUID().toString(), question)); status = "回答已生成" } catch (e: Exception) { status = e.message ?: "请求失败" } } }, modifier = Modifier.fillMaxWidth()) { Text("发送") }; Text(status); LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) { items(answers) { Card(Modifier.fillMaxWidth()) { Text(it, Modifier.padding(14.dp)) } } } }
                    1 -> { Text("健康数据", style = MaterialTheme.typography.headlineSmall); Text("从 Android Health Connect 读取最近 30 天步数和体重，并同步到同一账号。"); Button(onClick = { permissions.launch(health.permissions) }, modifier = Modifier.fillMaxWidth()) { Text("授权并同步") }; OutlinedButton(onClick = { scanner.launch(ScanOptions().setPrompt("扫描网页上的 EviLife 配对二维码").setBeepEnabled(true)) }, modifier = Modifier.fillMaxWidth()) { Text("扫码绑定网页账号") }; Text(status) }
                    else -> { Text("设置", style = MaterialTheme.typography.headlineSmall); OutlinedTextField(api.baseUrl, { api.baseUrl = it }, label = { Text("服务器地址") }, modifier = Modifier.fillMaxWidth()); Text("当前账号：$email"); Text("健康权限由系统 Health Connect 管理。") }
                }
            }
        }
    }
}

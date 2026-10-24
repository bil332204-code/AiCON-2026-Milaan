import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir: '.', testMatch: '*.spec.mjs', timeout: 60000, workers: 1,
  use: {baseURL:'http://127.0.0.1:8765', headless:true, trace:'retain-on-failure',
    launchOptions: process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{}},
  projects: [
    {name:'desktop',use:{viewport:{width:1440,height:1000}}},
    {name:'mobile',use:{viewport:{width:390,height:844},isMobile:true,hasTouch:true}}
  ],
  webServer: {command:(process.env.MILAAN_TEST_PYTHON||'../../.venv/bin/python')+' serve.py',url:'http://127.0.0.1:8765/api/health',reuseExistingServer:false,timeout:30000}
});

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S6 验收③：驱动原型 quiz.html 拍到与真机同名的五种状态（390 宽的手机框）。

真机截图在 shots/ 下由 e2e-quiz.py 产出（390×844 视口），这里拍原型的同一批状态，
交给 make-side-by-side.py 拼成并排图（cmp-390-*.png）。

原型必须走 http（file:// 下 localStorage.setItem 会抛 SecurityError，结算存档写不进去），
所以由 run-acceptance.sh 先起 python -m http.server 8099 指向原型目录。

用法：python proto-shots.py <原型 http 根地址>
"""
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8099'
VIEW = {'width': 480, 'height': 1000}  # 留出边距，让 390×844 的手机框完整入镜


def shot(page, name):
    path = os.path.join(HERE, 'shots', name)
    page.locator('#phone').screenshot(path=path)
    print('    · 原型截图 shots/{}'.format(name))


def open_level(page, level):
    page.goto('{}?level={}'.format(ROOT.rstrip('/') + '/quiz.html', level))
    page.wait_for_selector('#opts .opt')
    page.wait_for_timeout(150)


def answer(page, correct=True):
    """点一次选项（按原型自己的 curAns 定位正确答案），等反馈条出来。"""
    js = ("const els=[...document.querySelectorAll('.opt')];"
          "const i = %s; els[i].click();" % ('curAns' if correct else '(curAns+1)%els.length'))
    page.evaluate(js)
    page.wait_for_selector('.feedback.show', timeout=5000)
    page.wait_for_timeout(250)


def finish_level(page, correct=True):
    """把整关按同一对错策略答完 → 走到结算层。"""
    n = page.evaluate('QS.length')
    for i in range(n):
        answer(page, correct=correct)
        if i < n - 1:
            page.evaluate('next()')
            page.wait_for_timeout(120)
    page.evaluate('next()')          # 最后一题：继续 → finish()
    page.wait_for_timeout(400)


def main():
    os.makedirs(os.path.join(HERE, 'shots'), exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport=VIEW, device_scale_factor=1)

        print('== 原型 quiz.html · 第 1 关（高频词，5 题）==')
        open_level(page, 1)
        shot(page, 'proto-question.png')
        answer(page, correct=True)
        shot(page, 'proto-feedback-ok.png')
        page.evaluate('next()')
        page.wait_for_timeout(150)
        answer(page, correct=False)
        shot(page, 'proto-feedback-no.png')

        print('== 原型 quiz.html · 第 1 关全对（通关结算）==')
        open_level(page, 1)
        finish_level(page, correct=True)
        shot(page, 'proto-settlement-clear.png')

        print('== 原型 quiz.html · 第 1 关连错 3 题（爱心扣完）==')
        open_level(page, 1)
        for i in range(3):
            answer(page, correct=False)
            if i < 2:
                page.evaluate('next()')
                page.wait_for_timeout(150)
        page.wait_for_selector('#failOverlay:not([hidden])', timeout=5000)
        page.wait_for_timeout(250)
        shot(page, 'proto-settlement-fail.png')

        print('== 原型 quiz.html · 第 6 关（单元 Boss 真题混合卷）==')
        open_level(page, 6)
        finish_level(page, correct=True)
        shot(page, 'proto-settlement-boss.png')

        browser.close()
    print('')
    print('原型五态截图完成（shots/proto-*.png）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
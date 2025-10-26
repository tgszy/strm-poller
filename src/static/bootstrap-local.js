// 简化的Bootstrap JavaScript功能 - 本地版本

// 模态框功能
class Modal {
    constructor(element) {
        this._element = element;
        this._isShown = false;
        this._init();
    }
    
    _init() {
        // 添加关闭事件监听
        const closeButtons = this._element.querySelectorAll('[data-bs-dismiss="modal"]');
        closeButtons.forEach(button => {
            button.addEventListener('click', () => this.hide());
        });
        
        // 点击模态框外部关闭
        this._element.addEventListener('click', (e) => {
            if (e.target === this._element) {
                this.hide();
            }
        });
    }
    
    show() {
        this._element.style.display = 'block';
        this._element.classList.add('show');
        this._isShown = true;
        document.body.classList.add('modal-open');
    }
    
    hide() {
        this._element.style.display = 'none';
        this._element.classList.remove('show');
        this._isShown = false;
        document.body.classList.remove('modal-open');
    }
    
    toggle() {
        if (this._isShown) {
            this.hide();
        } else {
            this.show();
        }
    }
}

// 模态框初始化
function initModals() {
    const modalElements = document.querySelectorAll('.modal');
    modalElements.forEach(modalElement => {
        new Modal(modalElement);
    });
    
    // 模态框触发器
    const modalTriggers = document.querySelectorAll('[data-bs-toggle="modal"]');
    modalTriggers.forEach(trigger => {
        trigger.addEventListener('click', function() {
            const targetId = this.getAttribute('data-bs-target');
            const targetModal = document.querySelector(targetId);
            if (targetModal) {
                const modal = new Modal(targetModal);
                modal.show();
            }
        });
    });
}

// 折叠功能
class Collapse {
    constructor(element) {
        this._element = element;
        this._isShown = false;
        this._init();
    }
    
    _init() {
        // 添加切换事件监听
        const toggleButtons = document.querySelectorAll('[data-bs-toggle="collapse"][data-bs-target="#' + this._element.id + '"]');
        toggleButtons.forEach(button => {
            button.addEventListener('click', () => this.toggle());
        });
    }
    
    show() {
        this._element.style.display = 'block';
        this._element.classList.add('show');
        this._isShown = true;
    }
    
    hide() {
        this._element.style.display = 'none';
        this._element.classList.remove('show');
        this._isShown = false;
    }
    
    toggle() {
        if (this._isShown) {
            this.hide();
        } else {
            this.show();
        }
    }
}

// 折叠初始化
function initCollapses() {
    const collapseElements = document.querySelectorAll('.collapse');
    collapseElements.forEach(collapseElement => {
        new Collapse(collapseElement);
    });
}

// 工具提示功能
class Tooltip {
    constructor(element) {
        this._element = element;
        this._tooltip = null;
        this._init();
    }
    
    _init() {
        this._element.addEventListener('mouseenter', () => this.show());
        this._element.addEventListener('mouseleave', () => this.hide());
    }
    
    show() {
        const title = this._element.getAttribute('title') || this._element.getAttribute('data-bs-original-title');
        if (!title) return;
        
        this._tooltip = document.createElement('div');
        this._tooltip.className = 'tooltip bs-tooltip-top';
        this._tooltip.innerHTML = `
            <div class="tooltip-arrow"></div>
            <div class="tooltip-inner">${title}</div>
        `;
        
        document.body.appendChild(this._tooltip);
        
        // 定位
        const rect = this._element.getBoundingClientRect();
        this._tooltip.style.position = 'absolute';
        this._tooltip.style.top = (rect.top - this._tooltip.offsetHeight - 5) + 'px';
        this._tooltip.style.left = (rect.left + rect.width / 2 - this._tooltip.offsetWidth / 2) + 'px';
        this._tooltip.style.opacity = '1';
    }
    
    hide() {
        if (this._tooltip) {
            this._tooltip.remove();
            this._tooltip = null;
        }
    }
}

// 工具提示初始化
function initTooltips() {
    const tooltipElements = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipElements.forEach(tooltipElement => {
        new Tooltip(tooltipElement);
    });
}

// 页面加载完成后初始化所有组件
document.addEventListener('DOMContentLoaded', function() {
    initModals();
    initCollapses();
    initTooltips();
});

// 导出到全局作用域
window.bootstrap = {
    Modal: Modal,
    Collapse: Collapse,
    Tooltip: Tooltip
};
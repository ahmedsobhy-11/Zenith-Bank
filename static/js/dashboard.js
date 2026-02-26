document.addEventListener("DOMContentLoaded", () => {

    initBalance();
    initCreditScore();
    initChart();
    generateAIInsights();

});

/* ================= BALANCE ================= */

function initBalance(){
    const balanceEl = document.getElementById("liveBalance");

    let total = transactionsData.reduce((sum, tx)=> sum + parseFloat(tx.amount), 0);

    animateBalance(balanceEl, total);
}

function animateBalance(el, target){
    let current = 0;
    const step = target / 60;

    const counter = setInterval(()=>{
        current += step;
        el.innerText = "$" + Math.floor(current).toLocaleString();

        if(Math.abs(target - current) < 5){
            el.innerText = "$" + target.toLocaleString();
            clearInterval(counter);
        }
    },20);
}

/* ================= CREDIT SCORE ================= */

function initCreditScore(){
    const scoreEl = document.getElementById("scoreValue");
    const circle = document.getElementById("scoreCircle");
    const label = document.getElementById("scoreLabel");

    let income = transactionsData.filter(t=>t.amount>0).length;
    let expense = transactionsData.filter(t=>t.amount<0).length;

    let score = 600 + (income-expense)*10;
    if(score<300) score=300;
    if(score>850) score=850;

    let current=0;
    const step=score/60;

    const interval=setInterval(()=>{
        current+=step;
        scoreEl.innerText=Math.floor(current);
        if(current>=score){
            scoreEl.innerText=score;
            clearInterval(interval);
        }
    },20);

    if(score<500){
        circle.classList.add("score-poor");
        label.innerText="Poor";
    }else if(score<700){
        circle.classList.add("score-fair");
        label.innerText="Fair";
    }else{
        circle.classList.add("score-good");
        label.innerText="Excellent";
    }
}

/* ================= AI INSIGHTS ================= */

function generateAIInsights(){
    const list = document.getElementById("insightsList");

    let totalIncome = 0;
    let totalExpense = 0;

    transactionsData.forEach(tx=>{
        if(tx.amount>0) totalIncome+=parseFloat(tx.amount);
        else totalExpense+=Math.abs(parseFloat(tx.amount));
    });

    let saving = totalIncome-totalExpense;

    list.innerHTML="";

    addInsight(`Total Income: $${totalIncome}`);
    addInsight(`Total Expenses: $${totalExpense}`);

    if(saving>0){
        addInsight(`✅ You saved $${saving} this period.`);
    }else{
        addInsight(`⚠ You overspent by $${Math.abs(saving)}.`);
    }

    if(totalExpense > totalIncome*0.7){
        addInsight("⚠ Spending is higher than recommended.");
    }
}

function addInsight(text){
    const li=document.createElement("li");
    li.innerText=text;
    document.getElementById("insightsList").appendChild(li);
}

/* ================= CHART ================= */

function initChart(){
    const ctx=document.getElementById("financeChart");

    const monthly=transactionsData.slice(-6).map(tx=>tx.amount);

    new Chart(ctx,{
        type:"line",
        data:{
            labels:["1","2","3","4","5","6"],
            datasets:[{
                data:monthly,
                borderColor:"#3b82f6",
                backgroundColor:"rgba(59,130,246,0.2)",
                fill:true,
                tension:0.4
            }]
        },
        options:{
            plugins:{legend:{display:false}},
            responsive:true
        }
    });
}

/* ================= FAB ================= */

function showQuickMenu(){
    showNotification("Quick Actions Coming Soon 🚀");
}

/* ================= NOTIFICATIONS ================= */

function showNotification(text){
    const container=document.getElementById("notificationContainer");
    const note=document.createElement("div");
    note.className="notification";
    note.innerText=text;
    container.appendChild(note);

    setTimeout(()=>note.remove(),3000);
}
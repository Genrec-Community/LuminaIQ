// Razorpay Checkout (https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/)
const SCRIPT = 'https://checkout.razorpay.com/v1/checkout.js';
let loading = null;

export const loadRazorpay = () => {
    if (window.Razorpay) return Promise.resolve(true);
    if (!loading) {
        loading = new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = SCRIPT;
            s.onload = () => resolve(true);
            s.onerror = () => { loading = null; reject(new Error('Could not load the payment window. Check your connection.')); };
            document.body.appendChild(s);
        });
    }
    return loading;
};

/**
 * Open Checkout. Resolves with Razorpay's success payload
 * ({razorpay_payment_id, razorpay_signature, razorpay_subscription_id | razorpay_order_id});
 * rejects with {dismissed: true} if the student closes it, or an Error on failure.
 */
export const openCheckout = async (options) => {
    await loadRazorpay();
    return new Promise((resolve, reject) => {
        const rzp = new window.Razorpay({
            ...options,
            theme: { color: 'var(--lumina-accent)' },
            handler: (response) => resolve(response),
            modal: { ondismiss: () => reject({ dismissed: true }), confirm_close: true },
        });
        rzp.on('payment.failed', (resp) => reject(new Error(resp?.error?.description || 'Payment failed')));
        rzp.open();
    });
};

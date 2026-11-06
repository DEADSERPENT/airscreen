package com.airscreen.ui

import android.animation.ObjectAnimator
import android.animation.ValueAnimator
import android.content.Context
import android.util.AttributeSet
import android.view.View
import android.view.animation.AccelerateDecelerateInterpolator
import android.widget.FrameLayout
import android.widget.ImageView
import com.airscreen.R

/**
 * Abstract monochrome backdrop: soft light pools + two layers of flowing contour lines that drift very slowly
 * in opposite directions (parallax). Pre-rendered and dithered, so the TV panel shows no banding.
 *
 * Motion runs only while this view is actually visible and animations are enabled; once video starts the screens
 * are hidden, the animators are cancelled, and nothing here costs the decoder any GPU time.
 */
class AbstractBackground @JvmOverloads constructor(context: Context, attrs: AttributeSet? = null) : FrameLayout(context, attrs) {

    private val base = ImageView(context).apply { scaleType = ImageView.ScaleType.CENTER_CROP; setImageResource(R.drawable.ambient_glow) }
    private val linesA = contourLayer(R.drawable.bg_contours_a)
    private val linesB = contourLayer(R.drawable.bg_contours_b)
    private val animators = ArrayList<ObjectAnimator>()

    init {
        listOf(base, linesA, linesB).forEach { addView(it, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT)) }
    }

    private fun contourLayer(res: Int) = ImageView(context).apply {
        scaleType = ImageView.ScaleType.CENTER_CROP
        setImageResource(res)
        scaleX = 1.14f; scaleY = 1.14f          // oversize so drifting never reveals an edge
    }

    override fun onVisibilityChanged(changedView: View, visibility: Int) {
        super.onVisibilityChanged(changedView, visibility)
        refresh()
    }

    override fun onAttachedToWindow() { super.onAttachedToWindow(); refresh() }
    override fun onDetachedFromWindow() { stop(); super.onDetachedFromWindow() }
    override fun onWindowVisibilityChanged(visibility: Int) { super.onWindowVisibilityChanged(visibility); refresh() }

    private fun refresh() {
        if (isShown && windowVisibility == View.VISIBLE && ValueAnimator.areAnimatorsEnabled()) start() else stop()
    }

    private fun start() {
        if (animators.isNotEmpty()) return
        val d = resources.displayMetrics.density
        animators += drift(linesA, "translationX", -26f * d, 26f * d, 46_000)
        animators += drift(linesA, "translationY", -14f * d, 14f * d, 63_000)
        animators += drift(linesB, "translationX", 30f * d, -30f * d, 58_000)
        animators += drift(linesB, "translationY", 12f * d, -12f * d, 41_000)
        animators += drift(linesB, "alpha", 0.45f, 1f, 9_000)         // slow breathing
        linesA.setLayerType(LAYER_TYPE_HARDWARE, null)
        linesB.setLayerType(LAYER_TYPE_HARDWARE, null)
    }

    private fun drift(v: View, prop: String, from: Float, to: Float, ms: Long): ObjectAnimator =
        ObjectAnimator.ofFloat(v, prop, from, to).apply {
            duration = ms; repeatMode = ValueAnimator.REVERSE; repeatCount = ValueAnimator.INFINITE
            interpolator = AccelerateDecelerateInterpolator(); start()
        }

    private fun stop() {
        if (animators.isEmpty()) return
        animators.forEach { it.cancel() }
        animators.clear()
        linesA.setLayerType(LAYER_TYPE_NONE, null)
        linesB.setLayerType(LAYER_TYPE_NONE, null)
    }
}

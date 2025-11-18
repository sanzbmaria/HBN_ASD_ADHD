        echo "Processing parcel ${parcel}/360..."

        docker run --rm \
            -v "${INPUT_ROOT}":/data/inputs:ro \
            -v "${OUTPUT_ROOT}":/data/outputs \
            -e BASE_OUTDIR="${BASE_OUTDIR}" \
            -e N_JOBS="${N_JOBS}" \
            -e POOL_NUM="${POOL_NUM}" \
            -w /app/hyperalignment_scripts \
            ${IMAGE_NAME} \
            python run_hyperalignment.py ${parcel} ${HYPERALIGNMENT_MODE} \
            2>&1 | tee "${OUTPUT_ROOT}/logs/hyperalignment_parcel_${parcel}.log"
    done

    echo "✓ Hyperalignment complete"
fi

###############################################
# STEP 4 — BUILD CHA CONNECTOMES
###############################################

if [ "${RUN_CHA_CONNECTOMES}" = "yes" ]; then
    echo ""
    echo "======= STEP 4: BUILD CHA CONNECTOMES ======="

    docker run --rm \
        -v "${INPUT_ROOT}":/data/inputs:ro \
        -v "${OUTPUT_ROOT}":/data/outputs \
        -e BASE_OUTDIR="${BASE_OUTDIR}" \
        -e N_JOBS="${N_JOBS}" \
        -w /app/hyperalignment_scripts \
        ${IMAGE_NAME} \
        python3 build_CHA_connectomes.py --mode ${CHA_CONNECTOME_MODE} \
        2>&1 | tee "${OUTPUT_ROOT}/logs/build_cha_connectomes.log"

    echo "✓ CHA connectomes built"
fi

###############################################
# SUMMARY
###############################################

echo ""
echo "================================================"
echo "PIPELINE COMPLETE"
echo "================================================"
echo ""
echo "Results in:"
echo "  ${OUTPUT_ROOT}/glasser_ptseries/"
echo "  ${OUTPUT_ROOT}/connectomes/"
echo "  ${OUTPUT_ROOT}/connectomes/hyperalignment_output/"
echo ""
echo "Logs: ${OUTPUT_ROOT}/logs/"
echo ""

"./full_pipeline.sh" 159L, 4777B                                                                                                                                            159,0-1       Bot
